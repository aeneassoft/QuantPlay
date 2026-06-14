"""Deep analysis of the human's real sessions: meta-pattern, when they beat the bot vs
when the bot exploited their playful style, and tilt over time. Uses Claude for the narrative.

Run:  python -m pokerbot.analysis.session_deep
"""
from __future__ import annotations

import glob
import json
import os

from pokerbot import config
from pokerbot.analysis.session_analysis import compute_stats


def user_sessions():
    files = sorted(glob.glob(str(config.DATA_DIR / "sessions" / "*.jsonl")), key=os.path.getmtime)
    out = []
    for f in files:
        recs = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
        if not recs:
            continue
        hraise = sum(1 for r in recs for a in r["actions"]
                     if a["is_human"] and a["action"] in ("bet", "raise"))
        if hraise > 0:                       # real human play (my automated tests never raised)
            out.append((os.path.basename(f), recs))
    return out


def hnet(rec) -> float:
    hs = str(rec["human_seat"])
    return rec["net"].get(hs, 0)


def fmt_hand(rec) -> str:
    hs = str(rec["human_seat"]); bb = rec["bb"]
    pos = rec["positions"].get(hs, "?")
    hole = " ".join(rec["hole"].get(hs, []))
    seq = []
    for a in rec["actions"]:
        nm = "DU" if a["is_human"] else rec["positions"].get(str(a["seat"]), "?")
        amt = f" {a['amount']/bb:.1f}" if a.get("amount") else ""
        seq.append(f"{a['street'][:2]}·{nm} {a['action']}{amt}")
    res = rec.get("result", {})
    wins = ", ".join(f"{w['name']}({w.get('rank', '')})" for w in res.get("winners", []))
    return (f"#{rec['hand_no']} {pos} [{hole}] board[{' '.join(rec['board'])}] | "
            f"{' '.join(seq)} | {res.get('reason')}: {wins} | DU {hnet(rec)/bb:+.1f}bb")


def narrative(stats, arc, wins, losses) -> str:
    if not config.ANTHROPIC_API_KEY:
        return "(kein Claude-Key)"
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    sys = (
        "Du bist ein scharfsinniger Poker-Coach. Analysiere die Spielweise eines FREIZEIT-Spielers "
        "(6-max, gegen unseren Bot) anhand der Aggregat-Statistik, des Session-Verlaufs (zeigt evtl. "
        "Tilt) und konkreter Beispielhände. Antworte auf Deutsch, konkret, mit Bezug auf die Zahlen "
        "und einzelne Beispielhände. Struktur:\n"
        "1) META-MUSTER: Welcher Spielstil-Archetyp und das Kern-Muster hinter seinen Entscheidungen.\n"
        "2) WANN ER BESSER WAR ALS DER BOT: konkrete Hände/Situationen, in denen er den Bot überspielt hat.\n"
        "3) WANN DER BOT IHN AUSGENUTZT HAT: wie der Bot die spielerische/lockere Spielweise bestraft hat.\n"
        "4) TILT: ob der Verlauf Tilt zeigt (steigende Verluste/Aggression zum Ende).\n"
        "5) Drei konkrete, umsetzbare Tipps."
    )
    user = (f"AGGREGAT-STATISTIK:\n{json.dumps(stats, ensure_ascii=False, indent=1)}\n\n"
            f"SESSION-VERLAUF (chronologisch, zeigt Tilt):\n" +
            "\n".join(arc) +
            f"\n\nGRÖSSTE GEWINN-HÄNDE:\n" + "\n".join(wins) +
            f"\n\nGRÖSSTE VERLUST-HÄNDE:\n" + "\n".join(losses))
    msg = client.messages.create(model=config.CLAUDE_MODEL, max_tokens=2600, system=sys,
                                 messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def main() -> None:
    sessions = user_sessions()
    all_recs = [r for _, recs in sessions for r in recs]
    print(f"Echte Sessions: {len(sessions)} | Hände gesamt: {len(all_recs)}")
    arc = []
    for name, recs in sessions:
        bb = recs[0]["bb"]
        net = sum(hnet(r) for r in recs) / bb
        arc.append(f"  {name.replace('session_','').replace('.jsonl','')}: {len(recs):3d} Hände, "
                   f"{net:+.0f}bb ({net/len(recs)*100:+.0f} bb/100)")
    print("Verlauf:"); print("\n".join(arc))

    stats = compute_stats(all_recs)
    print("\nAggregat:", json.dumps({k: stats[k] for k in
          ("hands", "vpip_pct", "pfr_pct", "threebet_pct", "postflop_aggression_factor",
           "went_to_showdown_pct", "bb_per_100")}, ensure_ascii=False))

    ranked = sorted(all_recs, key=hnet)
    losses = [fmt_hand(r) for r in ranked[:6]]
    wins = [fmt_hand(r) for r in ranked[-6:][::-1]]
    print("\n=== CLAUDE META-ANALYSE ===\n")
    print(narrative(stats, arc, wins, losses))


if __name__ == "__main__":
    main()
