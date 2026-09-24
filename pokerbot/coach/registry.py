"""Append-only trainer session registry (docs/plans/TRAINER_PLAN.md P0-6, doctrine docs/doctrine/TRAINER_DESIGN.md §4).

WHY: the single module-global SESSION dies wholesale on 'Neu' (six_server.py:125, recon gotcha #1) —
so session provenance (mode, flag fingerprint, file paths, final net) must live in an append-only
JSONL, never in memory. Rows reuse ``session_log.append_record`` verbatim (session_log.py:35-38).
BINDING (P0-6 header): the mode is read from the SESSION (set per request by P0-0), never from an
env variable. Write failures degrade to a stderr warning — the registry must never break play.

Run:  python -m pokerbot.coach.registry      (self-test: synthetic sessions, no server needed)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from pokerbot import config
from pokerbot.strategy import gto_mode
from pokerbot.web import session_log

REGISTRY_PATH = config.DATA_DIR / "trainer" / "registry.jsonl"
# six_server's hardcoded seat->profile assignment (six_server.py:37) — the fallback when the
# session's bots are not introspectable; recorded so the P2 difficulty controller has provenance.
DEFAULT_PROFILE_ASSIGN = {1: "tag", 2: "lag", 3: "nit", 4: "station", 5: "maniac"}


def _now() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def _session_id(session) -> str:
    sid = getattr(session, "session_id", None)
    if sid:
        return str(sid)
    path = getattr(session, "path", None)                      # session_<sid>.jsonl -> <sid>
    return Path(path).stem.removeprefix("session_") if path else "unknown"


def _decisions_path(session) -> str | None:
    dp = getattr(session, "decisions_path", None)
    if dp:
        return str(dp)
    path = getattr(session, "path", None)                      # P0-1 step 4 naming convention
    if path is None:
        return None
    p = Path(path)
    return str(p.with_name("decisions_" + p.stem.removeprefix("session_") + ".jsonl"))


def _profile_assign(session) -> dict:
    try:                                                       # actual truth from the live bots (SixMaxBot.k.name)
        bots = getattr(session, "bots", None) or {}
        assign = {s: b.k.name for s, b in bots.items()}
        return assign or dict(DEFAULT_PROFILE_ASSIGN)
    except Exception:  # noqa: BLE001 — provenance is best-effort, never load-bearing
        return dict(DEFAULT_PROFILE_ASSIGN)


def register_start(session) -> dict | None:
    """Append the start row for a Session. Returns the row, or None on (warned) failure."""
    try:
        table = getattr(session, "table", None)
        stack_bb = (table.start_stack // table.bb) if table is not None else None
        row = {
            "event": "start",
            "session_id": _session_id(session),
            "ts": _now(),
            "mode": getattr(session, "mode", "gto"),           # BINDING: from the session, not env
            "stack_bb": stack_bb,
            "session_log_path": str(getattr(session, "path", "")) or None,
            "decisions_path": _decisions_path(session),
            "profile_assign": _profile_assign(session),
            "fingerprint": gto_mode.fingerprint(),             # gto_mode.py:135 — exact flag set per graded session
        }
        session_log.append_record(REGISTRY_PATH, row)
        return row
    except Exception as e:  # noqa: BLE001 — registry failure must never break /api/new_session
        print(f"[registry] WARNING: start row not written: {e!r}", file=sys.stderr)
        return None


def register_end(session) -> dict | None:
    """Append the end row for a Session (call before 'Neu' replaces it / at /api/analyze)."""
    try:
        row = {
            "event": "end",
            "session_id": _session_id(session),
            "ts": _now(),
            "hands_done": getattr(session, "hands_done", None),
            "human_net": getattr(session, "human_net", None),
        }
        session_log.append_record(REGISTRY_PATH, row)
        return row
    except Exception as e:  # noqa: BLE001
        print(f"[registry] WARNING: end row not written: {e!r}", file=sys.stderr)
        return None


def sessions(path: Path | None = None) -> list[dict]:
    """Fold start/end rows by session_id (last-writer-wins), in first-appearance order.

    Each entry = merged start fields + end fields + {'ended': bool}. Torn/corrupt lines are skipped
    (append-only file, a crash mid-write must not poison the reader).
    """
    path = Path(path) if path is not None else REGISTRY_PATH
    if not path.exists():
        return []
    folded: dict[str, dict] = {}
    order: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = row.get("session_id")
        if not sid or row.get("event") not in ("start", "end"):
            continue
        if sid not in folded:
            folded[sid] = {"session_id": sid, "ended": False}
            order.append(sid)
        entry = folded[sid]
        entry.update({k: v for k, v in row.items() if k != "event"})
        if row["event"] == "end":
            entry["ended"] = True
    return [folded[s] for s in order]


# ----------------------------------------------------------------- offline self-test (no server)
def _selftest() -> None:
    import os
    import tempfile
    from types import SimpleNamespace

    global REGISTRY_PATH
    os.environ.setdefault("POKERB_PRINCE", "1")                # the grader process anchor (P0-2 sets it too)
    gto_mode.apply()

    with tempfile.TemporaryDirectory() as td:
        old_path = REGISTRY_PATH
        REGISTRY_PATH = Path(td) / "trainer" / "registry.jsonl"
        try:
            def fake_session(sid, mode=None, hands=0, net=0):
                s = SimpleNamespace(
                    session_id=sid,
                    path=Path(td) / "sessions" / f"session_{sid}.jsonl",
                    table=SimpleNamespace(start_stack=10000, bb=100),
                    bots={}, hands_done=hands, human_net=net)
                if mode is not None:
                    s.mode = mode
                return s

            s1 = fake_session("20260802_100000", mode="exploit")
            row = register_start(s1)
            assert row is not None and row["mode"] == "exploit", "mode must come from the session"
            assert row["stack_bb"] == 100
            assert row["decisions_path"].endswith("decisions_20260802_100000.jsonl")
            assert row["profile_assign"] == DEFAULT_PROFILE_ASSIGN       # empty bots -> fallback
            fp = row["fingerprint"]
            assert isinstance(fp, dict) and fp.get("POKERB_PRINCE") == "1" and "POKERB_EXPLOIT" in fp

            # play 3 hands -> end s1 BEFORE s2 starts ('Neu' replaces SESSION wholesale)
            s1.hands_done, s1.human_net = 3, -250
            assert register_end(s1) is not None
            s2 = fake_session("20260802_110000")               # no mode attr -> default 'gto', never env
            row2 = register_start(s2)
            assert row2 is not None and row2["mode"] == "gto"

            # reader folds correctly, tolerates a torn line
            with open(REGISTRY_PATH, "a", encoding="utf-8") as f:
                f.write('{"torn json...\n')
            got = sessions()
            assert [g["session_id"] for g in got] == ["20260802_100000", "20260802_110000"]
            first, second = got
            assert first["ended"] and first["hands_done"] == 3 and first["human_net"] == -250
            assert first["mode"] == "exploit" and first["decisions_path"] == row["decisions_path"]
            assert not second["ended"]

            # write failure degrades to a warning, never an exception (server 200 guarantee)
            real_append = session_log.append_record
            session_log.append_record = lambda *a, **k: (_ for _ in ()).throw(OSError("disk gone"))
            try:
                assert register_start(s1) is None and register_end(s1) is None
            finally:
                session_log.append_record = real_append

            # missing registry file -> empty list, no exception
            assert sessions(Path(td) / "nope.jsonl") == []
            print(f"OK - registry: start/end rows append-only, mode from session, "
                  f"{len(got)} sessions folded, write failure tolerated")
        finally:
            REGISTRY_PATH = old_path


if __name__ == "__main__":
    _selftest()
