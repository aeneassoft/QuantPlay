"""Targeted dig: human 3bets + opener response (verify read #3), all 44 hands, all session files."""
import glob
import json
import os

from pokerbot import config

files = sorted(glob.glob(str(config.DATA_DIR / "sessions" / "session_*.jsonl")), key=os.path.getmtime)
print(len(files), "session files total:", [os.path.basename(f) for f in files])
for f in files:
    hands = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
    for h in hands:
        human = h["human_seat"]
        pre = [a for a in h["actions"] if a["street"] == "preflop"]
        for i, a in enumerate(pre):
            if a["action"] == "raise" and a["seat"] == human:
                prior = [x for x in pre[:i] if x["action"] == "raise"]
                kind = f"3bet+ (over {prior[0]['pos']} {prior[0]['amount']})" if prior else "OPEN"
                after = [x for x in pre[i + 1:] if prior and x["seat"] == prior[0]["seat"]]
                resp = (after[0]["action"] if after else "—")
                print(f"{os.path.basename(f)} h{h['hand_no']}: YOU raise {a['amount']} pos {a['pos']} [{kind}] "
                      f"-> opener {resp}; your net {h['net'].get(str(human))}")
        for s, hole in h["hole"].items():
            if hole[0][0] == "4" and hole[1][0] == "4":
                acts = [(x["street"], x["action"], x["amount"]) for x in h["actions"] if x["seat"] == int(s)]
                print(f"  {os.path.basename(f)} h{h['hand_no']}: seat{s}({h['positions'][s]}) had 44 "
                      f"acts={acts} net={h['net'].get(s)} winners={[w['seat'] for w in h['result'].get('winners', [])]}")
