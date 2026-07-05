"""ISOLATED GTOW-vs-GLM pod — the OWN-AI headline number. Serves our TRAINED GLM-Z1-9B (the GRPO adapter MERGED into
the base) with vLLM, then runs the gtow_client `--agent-type glm` vs GTO Wizard => AIVAT bb/100. Mirrors the engine+brain
seam that gave Claude -28.55, only the brain is OUR model (run on the pod, not a frontier API).

WHY MERGE (not vLLM --enable-lora): merging the LoRA into the base is DETERMINISTIC and removes the vLLM-Glm4-LoRA
support unknown -> no paid debugging of --lora-modules. The ~18GB merged write fits the 80GB disk.

CRITICAL ISOLATION (CLAUDE.md cross-kill hazard): launches via the RAW API WITHOUT `R._track`, and kills ONLY its own id
(`R._req("DELETE", ...)`) -- NEVER `R.kill()`. So a concurrently-running pod is never touched.

KEY HYGIENE: the GTOW key is written to a local temp -> scp'd to /root/.gtow_key -> read on the pod via
`$(cat /root/.gtow_key)`. It NEVER appears in a printed command, an env dump, or this repo. The local temp is deleted
immediately after the upload.

Run:   python -m infra.gtow_glm_pod                 # smoke 10 -> if clean, full 100
       python -m infra.gtow_glm_pod --smoke 10 --full 200
       GLM_USE_SFT=1 python -m infra.gtow_glm_pod   # test the SFT warm-start instead of the RL'd adapter
Verify after:  python -m infra.runpod_run --status  (must show no NEW tracked pod -- this one is untracked + self-killed)
"""
from __future__ import annotations

import argparse
import atexit
import os
import subprocess
import time

from infra import runpod_run as R
from infra.cfv_pod_campaign import _scp_down, _scp_up, _ssh, ssh_endpoint
from pipeline import orchestrate as O
from pokerbot import config

REMOTE = "/root/pokerb"
HARD_CAP_S = int(os.environ.get("GTOW_HARD_CAP", "7200"))    # 2h wall (setup ~12m + base DL ~5m + merge ~5m + vLLM ~5m + run)
GPU = os.environ.get("GTOW_GPU", "NVIDIA H100 80GB HBM3")    # the reliable SXM; set "" to fall back to the R.FAST chain
GLM_BASE_HF = os.environ.get("GLM_BASE_HF", "THUDM/GLM-Z1-9B-0414")
USE_SFT = os.environ.get("GLM_USE_SFT", "0") == "1"          # default = the RL'd (GRPO) adapter; the SFT warm-start for A/B
# GLM_ADAPTER_TGZ = an EXPLICIT adapter tgz to serve (overrides the slim defaults) — for A/B-ing specific run outputs
# (e.g. a fresh campaign's qwen_poker_grpo_live.tgz vs sft_new.tgz). Must untar to a checkpoint-*/ or qwen_poker_lora/ dir.
_ADP_OVERRIDE = os.environ.get("GLM_ADAPTER_TGZ", "")
ADAPTER_TGZ = ((config.ROOT / _ADP_OVERRIDE) if not os.path.isabs(_ADP_OVERRIDE) else __import__("pathlib").Path(_ADP_OVERRIDE)) \
    if _ADP_OVERRIDE else config.MODELS_DIR / ("sft_slim.tgz" if USE_SFT else "grpo_slim.tgz")
VLLM_PORT = 8000
MERGED = "/root/glm_merged"


def _launch_isolated(disk: int = 80):
    """Launch ONE GPU via the raw API -- deliberately NO `R._track`, so a training pod's session + `--kill` never see
    this pod (the cross-kill guard). Prefers the reliable H100 SXM (SECURE), then the R.FAST chain. Returns (pid, gpu)."""
    pub = open(R.PUBKEY_FILE, encoding="utf-8").read().strip()
    gpus = [GPU] if GPU else R.FAST
    for cloud in ("SECURE", "COMMUNITY"):
        for gpu in gpus:
            body = {"name": "pokerb-gtow-glm", "imageName": R.IMAGE, "cloudType": cloud, "computeType": "GPU",
                    "gpuTypeIds": [gpu], "gpuCount": 1, "containerDiskInGb": disk, "volumeInGb": 0,
                    "ports": ["22/tcp"], "env": {"PUBLIC_KEY": pub}}
            code, resp = R._req("POST", "/pods", body)
            if code in (200, 201):
                pid = resp.get("id")
                print(f"  launched ISOLATED GTOW-GLM pod {pid} on {gpu} [{cloud}] (${resp.get('costPerHr')}/hr) — NOT tracked",
                      flush=True)
                return pid, gpu
            print(f"  {cloud:9} {gpu:24}: {code} {str(resp)[:110]}", flush=True)
    return None, None


_state = {"killed": False}


def _kill_by_id(pid: str | None) -> None:
    """Terminate ONLY this pod (NEVER `R.kill()` — that would also kill a concurrent training pod). Idempotent."""
    if not pid or _state["killed"]:
        return
    _state["killed"] = True
    try:
        code, _ = R._req("DELETE", f"/pods/{pid}")
        print(f"  >>> GTOW-GLM pod {pid} TERMINATED (DELETE {code}). Any other pod untouched. <<<", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"  !! kill error for {pid} ({e}) — MANUALLY DELETE /pods/{pid} in the RunPod console", flush=True)


def _setup(ip: str, port: int) -> bool:
    """The LEAN vLLM-serving + merge + client stack (the pod_setup_rl.sh TEACHER recipe + peft for the merge + the
    gtow_client deps). The torch pin keeps the image's cu128 torch so pip resolves a compatible vLLM."""
    print("  >>> installing vLLM + merge + client deps ...", flush=True)
    # fastapi<0.137: vLLM 0.11.0 has no upper FastAPI pin, so pip grabs 0.137+, whose include_router() refactor (routes
    # become _IncludedRouter objects with no .path) crashes vLLM's prometheus middleware -> EVERY request 500s
    # (incl. /health + /v1/completions). vLLM's own fix is to cap fastapi<0.137. (vllm-project/vllm#45596)
    cmd = ("export PIP_BREAK_SYSTEM_PACKAGES=1 && cd /root && "
           "TORCH_PIN=$(python3 -c \"import torch;print('torch=='+torch.__version__.split('+')[0])\") && "
           "python3 -m pip install -q $TORCH_PIN vllm 'transformers>=4.55.2,<4.57' 'fastapi<0.137' hf_transfer peft "
           "accelerate treys numpy requests fire httpx pydantic structlog tenacity tqdm 2>&1 | tail -4 && "
           "python3 -c \"import torch,transformers,vllm,peft,fastapi; "
           "print('GTOW_DEPS_OK', torch.__version__, 'vllm', vllm.__version__, 'fastapi', fastapi.__version__)\"")
    r = _ssh(ip, port, cmd, timeout=1200)
    if "GTOW_DEPS_OK" not in (r.stdout or ""):
        print(f"  setup FAILED: {((r.stdout or '') + (r.stderr or ''))[-500:]}", flush=True)
        return False
    print("  " + [ln for ln in (r.stdout or "").splitlines() if "GTOW_DEPS_OK" in ln][-1], flush=True)
    return True


def _upload(ip: str, port: int) -> bool:
    """Bundle (pokerbot/research/...) + the gtow_client (src + pyproject, NOT .venv) + the adapter tgz + the GTOW key."""
    up = O.push(ip, port, O.build_tarball())                 # -> /root/pokerb/{pokerbot,research,training,...}
    if up.returncode != 0:
        print(f"  bundle push FAILED: {(up.stderr or '')[:200]}", flush=True)
        return False
    client_tgz = O.build_tarball(out_path=config.DATA_DIR / "gtow_client.tgz",
                                 members=["tools/gtow_client/src", "tools/gtow_client/pyproject.toml"])
    cu = O.push(ip, port, client_tgz, remote="/root/client.tgz")   # -> /root/pokerb/tools/gtow_client/{src,pyproject}
    if cu.returncode != 0:
        print(f"  client push FAILED: {(cu.stderr or '')[:200]}", flush=True)
        return False
    sc = None                                               # ~706MB slim adapter; the big PC->pod transfer is the one that
    for attempt in range(1, 4):                             # hits a transient "connection reset by peer" mid-stream -> retry
        sc = _scp_up(ip, port, [str(ADAPTER_TGZ)], "/root/")
        if sc.returncode == 0:
            break
        print(f"  adapter scp attempt {attempt}/3 failed: {((sc.stderr or '')[:160]).strip()}", flush=True)
        time.sleep(5)
    if not sc or sc.returncode != 0:
        print(f"  adapter scp FAILED after 3 attempts: {(sc.stderr or '')[:200] if sc else 'n/a'}", flush=True)
        return False
    if not _upload_key(ip, port):
        return False
    print(f"  uploaded bundle + client + adapter ({ADAPTER_TGZ.name}) + key", flush=True)
    return True


def _upload_key(ip: str, port: int) -> bool:
    """Write the GTOW key to a local temp -> scp -> delete the temp. The key NEVER touches a printed command or env dump."""
    key = config.GTOWIZARD_API_KEY
    if not key:
        print("  NO GTOW key (Secret keys / $GTOWIZARD_API_KEY); aborting.", flush=True)
        return False
    tmp = config.DATA_DIR / "_gtow_key.txt"
    tmp.write_text(key, encoding="utf-8")
    try:
        sc = _scp_up(ip, port, [str(tmp)], "/root/.gtow_key")
    finally:
        tmp.unlink(missing_ok=True)                          # never leave the key on disk
    if sc.returncode != 0:
        print(f"  key scp FAILED: {(sc.stderr or '')[:120]}", flush=True)
        return False
    return True


def _merge(ip: str, port: int) -> bool:
    """Untar the adapter, then merge it into the base on CPU (no GPU contention with the coming vLLM) -> /root/glm_merged.
    merge_and_unload folds the LoRA delta into the weights -> a plain full model vLLM serves with zero LoRA unknowns."""
    # --no-same-owner: grpo_slim.tgz was made with Git-Bash tar (Windows uid 197609); as root the chown-restore FAILS
    # ("Invalid argument") -> tar exits non-zero -> the && short-circuits. --no-same-owner skips the chown (exit 0).
    r = _ssh(ip, port, f"cd /root && tar --no-same-owner -xzf {ADAPTER_TGZ.name} && "
                       "(ls -d /root/checkpoint-* 2>/dev/null | tail -1; ls -d /root/qwen_poker_lora 2>/dev/null) | tail -1",
             timeout=180)
    adp = (r.stdout or "").strip().splitlines()[-1].strip() if (r.stdout or "").strip() else ""
    if not adp.startswith("/root/"):
        print(f"  adapter dir not found after untar: {((r.stdout or '') + (r.stderr or ''))[-200:]}", flush=True)
        return False
    print(f"  merging adapter {adp} into {GLM_BASE_HF} (CPU) ...", flush=True)
    merge = (
        "import torch, glob\n"
        "from transformers import AutoModelForCausalLM, AutoTokenizer\n"
        "from peft import PeftModel\n"
        f"BASE = {GLM_BASE_HF!r}\n"
        f"ADP = {adp!r}\n"
        "m = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16, device_map='cpu', low_cpu_mem_usage=True)\n"
        "m = PeftModel.from_pretrained(m, ADP)\n"
        "m = m.merge_and_unload()\n"
        f"m.save_pretrained({MERGED!r}, safe_serialization=True)\n"
        f"AutoTokenizer.from_pretrained(BASE, trust_remote_code=True).save_pretrained({MERGED!r})\n"
        "print('MERGE_OK')\n"
    )
    cmd = ("export PIP_BREAK_SYSTEM_PACKAGES=1 HF_HUB_ENABLE_HF_TRANSFER=1 HF_HUB_OFFLINE=0 && cd /root && "
           "python3 - <<'PY'\n" + merge + "PY")
    r = _ssh(ip, port, cmd, timeout=1800)                   # base download (~18GB) + CPU merge + save
    if "MERGE_OK" not in (r.stdout or ""):
        print(f"  MERGE FAILED: {((r.stdout or '') + (r.stderr or ''))[-600:]}", flush=True)
        return False
    print("  merge OK -> /root/glm_merged", flush=True)
    return True


def _serve(ip: str, port: int) -> bool:
    """Start vLLM (truly detached) on the merged model, then poll /health until it answers (a 9B loads in ~2-5 min).
    setsid + a subshell daemonizes it so the ssh start call returns promptly (a plain `nohup ... &` left the channel
    open last time -> a 120s hang). The TimeoutExpired guard is belt-and-suspenders: nohup keeps vLLM alive on the pod
    even if ssh won't close, so we fall through to /health, the REAL readiness check."""
    print("  >>> starting vLLM server ...", flush=True)
    start = (f"export PIP_BREAK_SYSTEM_PACKAGES=1 && cd /root && "
             f"(setsid nohup vllm serve {MERGED} --served-model-name glm --max-model-len 4096 "
             f"--gpu-memory-utilization 0.90 --dtype bfloat16 --trust-remote-code --port {VLLM_PORT} "
             f">/root/vllm.log 2>&1 </dev/null &) ; echo VLLM_LAUNCHED")
    try:
        _ssh(ip, port, start, timeout=60)
    except subprocess.TimeoutExpired:
        print("  (ssh start did not return promptly; vLLM is detached + launching — proceeding to /health)", flush=True)
    # poll /health; also break EARLY if the vllm process died (a load crash) so we don't burn the full 7.5 min.
    poll = (f"for i in $(seq 1 90); do curl -sf http://127.0.0.1:{VLLM_PORT}/health >/dev/null && "
            f"{{ echo VLLM_UP; break; }}; pgrep -f 'vllm serve' >/dev/null || {{ echo VLLM_DIED; break; }}; sleep 5; done")
    r = _ssh(ip, port, poll, timeout=600)
    if "VLLM_UP" not in (r.stdout or ""):
        why = "process DIED on load" if "VLLM_DIED" in (r.stdout or "") else "never became healthy in time"
        tail = _ssh(ip, port, "tail -40 /root/vllm.log", timeout=60)
        print(f"  vLLM {why}. log tail:\n{(tail.stdout or '')[-1400:]}", flush=True)
        return False
    print("  vLLM healthy on :%d (served as 'glm')" % VLLM_PORT, flush=True)
    return True


def _run_gtow(ip: str, port: int, n_hands: int, conc: int, budget_s: int, made_hand: bool | None = None,
              tocall_fix: bool | None = None, solver_freq: bool | None = None) -> str:
    """Run the gtow_client `--agent-type glm` (key from /root/.gtow_key via env, never the CLI). Returns the full output.
    `made_hand`/`tocall_fix`/`solver_freq` toggle the serve-time prompt features (POKERB_MADE_HAND / POKERB_TOCALL_FIX /
    POKERB_SOLVER_FREQ) — each None=production default / True / False, for the paired A/Bs."""
    mh = "" if made_hand is None else f"POKERB_MADE_HAND={1 if made_hand else 0} "
    tc = "" if tocall_fix is None else f"POKERB_TOCALL_FIX={1 if tocall_fix else 0} "
    sf = "" if solver_freq is None else f"POKERB_SOLVER_FREQ={1 if solver_freq else 0} "
    cmd = (f"cd {REMOTE}/tools/gtow_client/src && export GTOWIZARD_API_KEY=$(cat /root/.gtow_key) && "
           f"PYTHONPATH={REMOTE} GLM_VLLM_URL=http://127.0.0.1:{VLLM_PORT} GLM_MODEL=glm GLM_BASE={MERGED} "
           f"GLM_MODE=standard GLM_SOLVER_FLOOR=1 {mh}{tc}{sf}"
           f"python3 -m main --agent-type glm --num-hands {n_hands} --num-concurrent-hands {conc}")
    tags = ([f"made_hand={'ON' if made_hand else 'OFF'}"] if made_hand is not None else []) + \
           ([f"tocall_fix={'ON' if tocall_fix else 'OFF'}"] if tocall_fix is not None else []) + \
           ([f"solver_freq={'ON' if solver_freq else 'OFF'}"] if solver_freq is not None else [])
    tag = f" [{', '.join(tags)}]" if tags else ""
    print(f"  >>> GTOW run: {n_hands} hands, {conc} concurrent{tag} ...", flush=True)
    r = _ssh(ip, port, cmd, timeout=budget_s)
    out = (r.stdout or "") + "\n" + (r.stderr or "")
    for ln in out.splitlines():
        if any(k in ln for k in ("AIVAT", "RAW winnings", "GLM-BRAIN", "FLOW SPLIT", "Successful hands", "frac_bad",
                                 "Traceback", "Error", "per-hand spot log")):
            print("   " + ln.strip(), flush=True)
    return out


def _parse_aivat(out: str) -> str:
    """Pull the FINAL headline AIVAT bb/100 (± SE) line for the A/B summary; '' if absent. Prefer the 'AIVAT luck-adj'
    summary line — NOT the '[live] AIVAT running mean' progress lines (which would otherwise match first)."""
    final = [ln.strip() for ln in out.splitlines() if "AIVAT luck-adj" in ln]
    if final:
        return final[-1]
    cands = [ln.strip() for ln in out.splitlines()
             if "AIVAT" in ln and "bb/100" in ln and "running mean" not in ln]
    return cands[-1] if cands else ""


def _debug_capture(ip: str, port: int, budget_s: int) -> None:
    """Run a TINY sequential GTOW smoke with GLM_DEBUG=1 -> the RAW GLM completion + parse verdict PER decision. This is
    the frac_bad=1.0 diagnosis: it shows EXACTLY what the served model emits on real GTOW spots (reasoning prose? empty?
    truncated? wrong format?) so the fix is grounded, not guessed. max_tokens=512 rules out truncation; temp 0.0 = the
    failing config (override with GLM_GEN_TEMP)."""
    cmd = (f"cd {REMOTE}/tools/gtow_client/src && export GTOWIZARD_API_KEY=$(cat /root/.gtow_key) && "
           f"PYTHONPATH={REMOTE} GLM_VLLM_URL=http://127.0.0.1:{VLLM_PORT} GLM_MODEL=glm GLM_BASE={MERGED} "
           f"GLM_MODE=standard GLM_SOLVER_FLOOR=1 GLM_DEBUG=1 GLM_MAX_TOKENS=512 "
           f"GLM_GEN_TEMP={os.environ.get('GLM_GEN_TEMP', '0.0')} "
           f"python3 -m main --agent-type glm --num-hands 3 --num-concurrent-hands 1")
    print("  >>> DEBUG capture: 3 hands sequential, GLM_DEBUG=1 (raw completion + parse per decision) ...", flush=True)
    r = _ssh(ip, port, cmd, timeout=budget_s)
    out = (r.stdout or "") + "\n" + (r.stderr or "")
    (config.DATA_DIR / "gtow_glm_debug.txt").write_text(out, encoding="utf-8")   # save FIRST (real UTF-8; a print crash mustn't lose it)
    print("  full debug output -> data/gtow_glm_debug.txt (read it for the exact raws)", flush=True)
    for ln in out.splitlines():
        if any(k in ln for k in ("[GLM_DEBUG]", "RAW=", "PROG=", "GLM-BRAIN", "AIVAT", "Traceback", "Error")):
            print(("   " + ln).encode("ascii", "replace").decode("ascii"), flush=True)   # ascii-safe preview (Windows cp1252)


def _parse_frac_bad(out: str) -> float | None:
    """Pull frac_bad from the GLM-BRAIN report line = the served-model health gate. None if the line is absent."""
    import re
    m = re.search(r"frac_bad=([0-9.]+)", out)
    return float(m.group(1)) if m else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", type=int, default=int(os.environ.get("GTOW_SMOKE", "20")))   # 20: with the preflop switch the
    #                          smoke's frac_bad is POSTFLOP-only -> 10 gives too few postflop decisions for the fb>=0.5 gate
    ap.add_argument("--full", type=int, default=int(os.environ.get("GTOW_FULL", "100")))
    ap.add_argument("--conc", type=int, default=int(os.environ.get("GTOW_CONC", "8")))
    ap.add_argument("--debug", action="store_true",
                    help="serve -> 3-hand GLM_DEBUG capture (raw completions + parse) -> kill; NO full run")
    ap.add_argument("--ab", action="store_true",
                    help="paired made-hand A/B: run --full hands with the engine hand-read OFF then ON (same pod)")
    ap.add_argument("--ab-tocall", action="store_true",
                    help="paired to_call-fix A/B: --full hands with POKERB_TOCALL_FIX OFF then ON (same pod; made-hand stays ON)")
    ap.add_argument("--ab-hints", action="store_true",
                    help="paired solver_freq-hint A/B: POKERB_SOLVER_FREQ OFF then ON (same pod; made-hand+to_call ON both; OFF arm = the −28.36 baseline)")
    a = ap.parse_args()
    t0 = time.time()

    if not ADAPTER_TGZ.exists():
        print(f"adapter {ADAPTER_TGZ} missing; aborting (no cost).", flush=True)
        return
    if not (config.ROOT / "tools/gtow_client/src/main.py").exists():
        print("tools/gtow_client/src not found; aborting (no cost).", flush=True)
        return
    if not config.GTOWIZARD_API_KEY:
        print("NO GTOW key (Secret keys / $GTOWIZARD_API_KEY); aborting (no cost).", flush=True)
        return

    pid = {"id": None}
    atexit.register(lambda: _kill_by_id(pid["id"]))
    label = "SFT warm-start" if USE_SFT else "RL'd (GRPO)"
    print(f"ISOLATED GTOW-vs-GLM POD — our {label} GLM-Z1-9B (engine+brain) vs GTO Wizard "
          f"(smoke {a.smoke} -> full {a.full}). Never touches another pod.", flush=True)
    try:
        pid["id"], _gpu = _launch_isolated()
        if not pid["id"]:
            print("no pod launched (no cost).", flush=True)
            return
        ip, sport = ssh_endpoint(pid["id"])
        if not (ip and sport):
            print("pod never exposed SSH; aborting.", flush=True)
            return
        if not _setup(ip, sport):
            return
        if not _upload(ip, sport):
            return
        if not _merge(ip, sport):
            return
        if not _serve(ip, sport):
            return

        if a.debug:                                         # diagnose frac_bad: capture raw completions, then kill
            _debug_capture(ip, sport, max(300, int(HARD_CAP_S - (time.time() - t0) - 180)))
            return

        # SMOKE first: a tiny run proves the whole path (serve -> client -> GTOW -> AIVAT) + reveals frac_bad cheaply.
        smoke_budget = max(300, min(900, int(HARD_CAP_S - (time.time() - t0) - 1200)))
        smoke_out = _run_gtow(ip, sport, a.smoke, min(a.conc, a.smoke), smoke_budget)
        fb = _parse_frac_bad(smoke_out)
        if "AIVAT luck-adj" not in smoke_out:
            print("  SMOKE produced no AIVAT line — NOT proceeding (the path is broken). See the trace above.", flush=True)
            return
        if fb is not None and fb >= 0.5:                    # the GLM drove < half its decisions -> the full would just
            print(f"  SMOKE frac_bad={fb}: the GLM rarely drove (mostly the solver floor) — the served model looks OOD vs "
                  "the SFT/GRPO prompt. NOT running the full (it would measure the FLOOR, not the GLM). Debug alignment.",
                  flush=True)                               # measure the solver floor, not our model -> abort + report
            return
        print(f"  >>> SMOKE clean ({a.smoke} hands, frac_bad={fb}). Proceeding to the FULL run ({a.full} hands). <<<",
              flush=True)

        if a.ab:
            # PAIRED A/B in ONE session (same model, same pod, same GTOW opponent) -> isolates the made-hand fix's causal
            # effect at scale, cancelling card/session variance (the grounded-gate standard). OFF arm first, then ON.
            arm_budget = max(300, int((HARD_CAP_S - (time.time() - t0) - 240) / 2))
            on_out = _run_gtow(ip, sport, a.full, a.conc, arm_budget, made_hand=True)    # candidate first (secured if cut)
            off_out = _run_gtow(ip, sport, a.full, a.conc, arm_budget, made_hand=False)
            res_path = config.DATA_DIR / "gtow_glm_ab.txt"
            res_path.write_text("===== SMOKE =====\n" + smoke_out + "\n\n===== OFF (made_hand off) =====\n" + off_out
                                + "\n\n===== ON (made_hand on) =====\n" + on_out, encoding="utf-8")
            print(f"  A/B output -> {res_path.relative_to(config.ROOT)}", flush=True)
            print(f"\n  ===== MADE-HAND A/B (n={a.full}/arm, same model+pod+GTOW) =====", flush=True)
            print(f"   OFF (fix off): {_parse_aivat(off_out) or '(no AIVAT line)'}", flush=True)
            print(f"   ON  (fix on) : {_parse_aivat(on_out) or '(no AIVAT line)'}", flush=True)
            full_out = on_out                               # the production (ON) arm -> its per-hand log is pulled below
        elif a.ab_tocall:
            # PAIRED to_call-fix A/B (same model/pod/GTOW, made-hand ON in both) -> isolates the preflop to_call fix's
            # bb/100 effect, cancelling card variance. ON (fixed) first so it's secured if the wall-clock cuts the 2nd arm.
            arm_budget = max(300, int((HARD_CAP_S - (time.time() - t0) - 240) / 2))
            on_out = _run_gtow(ip, sport, a.full, a.conc, arm_budget, tocall_fix=True)
            off_out = _run_gtow(ip, sport, a.full, a.conc, arm_budget, tocall_fix=False)
            res_path = config.DATA_DIR / "gtow_glm_ab_tocall.txt"
            res_path.write_text("===== SMOKE =====\n" + smoke_out + "\n\n===== OFF (tocall_fix off = old bug) =====\n"
                                + off_out + "\n\n===== ON (tocall_fix on = committed-delta) =====\n" + on_out,
                                encoding="utf-8")
            print(f"  A/B output -> {res_path.relative_to(config.ROOT)}", flush=True)
            print(f"\n  ===== TO_CALL-FIX A/B (n={a.full}/arm, same model+pod+GTOW, made-hand ON) =====", flush=True)
            print(f"   OFF (bug: preflop to_call=whole pot): {_parse_aivat(off_out) or '(no AIVAT line)'}", flush=True)
            print(f"   ON  (fixed: committed-delta)        : {_parse_aivat(on_out) or '(no AIVAT line)'}", flush=True)
            full_out = on_out                               # pull the ON (fixed) arm's per-hand log below
        elif a.ab_hints:
            # PAIRED solver_freq-hint A/B (same model/pod/GTOW, made-hand + to_call ON in BOTH) -> isolates the new
            # serve-time advisor-bet-freq hint ON TOP of the −28.36 baseline. ON first (secured if the wall-clock cuts).
            arm_budget = max(300, int((HARD_CAP_S - (time.time() - t0) - 240) / 2))
            on_out = _run_gtow(ip, sport, a.full, a.conc, arm_budget, made_hand=True, tocall_fix=True, solver_freq=True)
            off_out = _run_gtow(ip, sport, a.full, a.conc, arm_budget, made_hand=True, tocall_fix=True, solver_freq=False)
            res_path = config.DATA_DIR / "gtow_glm_ab_hints.txt"
            res_path.write_text("===== SMOKE =====\n" + smoke_out
                                + "\n\n===== OFF (solver_freq off = −28.36 baseline) =====\n" + off_out
                                + "\n\n===== ON (solver_freq on = advisor bet-freq hint) =====\n" + on_out, encoding="utf-8")
            print(f"  A/B output -> {res_path.relative_to(config.ROOT)}", flush=True)
            print(f"\n  ===== SOLVER-FREQ HINT A/B (n={a.full}/arm, same model+pod+GTOW, made-hand+to_call ON) =====", flush=True)
            print(f"   OFF (no hint = protected baseline): {_parse_aivat(off_out) or '(no AIVAT line)'}", flush=True)
            print(f"   ON  (advisor bet-freq hint)       : {_parse_aivat(on_out) or '(no AIVAT line)'}", flush=True)
            full_out = on_out
        else:
            # FULL run with whatever wall-clock remains (minus a kill margin).
            full_budget = max(300, int(HARD_CAP_S - (time.time() - t0) - 180))
            full_out = _run_gtow(ip, sport, a.full, a.conc, full_budget)
            res_path = config.DATA_DIR / ("gtow_glm_sft.txt" if USE_SFT else "gtow_glm_grpo.txt")
            res_path.write_text(smoke_out + "\n\n===== FULL =====\n\n" + full_out, encoding="utf-8")
            print(f"  full output -> {res_path.relative_to(config.ROOT)}", flush=True)
        try:                                                # the per-hand spot log (which lines lose AIVAT) -> local
            tail = _ssh(ip, sport, "ls -t /root/pokerb/data/sessions/gtow_hands_*.jsonl 2>/dev/null | head -1", timeout=60)
            remote_log = (tail.stdout or "").strip().splitlines()
            if remote_log and remote_log[0].endswith(".jsonl"):
                _scp_down(ip, sport, remote_log[0], str(config.DATA_DIR / "sessions" / os.path.basename(remote_log[0])))
                print(f"  pulled per-hand log -> data/sessions/{os.path.basename(remote_log[0])}", flush=True)
        except Exception:  # noqa: BLE001
            pass
    finally:
        _kill_by_id(pid["id"])
        try:                                                # belt-and-suspenders: confirm via the API the pod is gone
            code, resp = R._req("GET", "/pods")
            pods = resp if isinstance(resp, list) else (resp.get("pods") or resp.get("data") or [])
            ids = [p.get("id") for p in pods] if code == 200 else []
            print(f"  API check: pod gone={pid['id'] not in ids} | pods now={ids}", flush=True)
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
