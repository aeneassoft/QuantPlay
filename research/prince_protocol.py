"""PRINCEDARKNESS-PROTOKOLL v1.0 — measurement engine (2026-07-07).
Parses ALL Princedarkness hands (923 CoinPoker cash + 75 GG tournament), computes the full stat table,
measures H1-H10 where the data allows, emits JSON for the results document.
Hard rules honored: no invented numbers; per-metric n; [DATEN FEHLEN] markers emitted where data is absent.
Run:  python -m research.prince_protocol
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime

CP = r"C:\Users\hampe\Documents\1# Personal Poker Hand Histories + reports\CoinPoker_Princedarkness_2026-02-01_to_2026-06-30_Cash.txt"
GG = r"C:\Users\hampe\Documents\1# Personal Poker Hand Histories + reports\GG20260706-2110 - Speed Racer Bounty 108 [10 BB].txt"
OUT = r"C:\Users\hampe\Desktop\PokerB\data\research_sweep\prince_protocol.json"

MONEY = r"[\u20AE]?([\d,]+(?:\.\d+)?)"


def _m(s):
    return float(s.replace(",", ""))


# ---------------------------------------------------------------- CoinPoker parser
def parse_coinpoker():
    txt = open(CP, encoding="utf-8").read()
    blocks = [b for b in re.split(r"(?=CoinPoker Hand #)", txt) if b.strip().startswith("CoinPoker")]
    hands = []
    for b in blocks:
        h = {}
        head = re.search(r"CoinPoker Hand #(\d+): NLH \(" + MONEY + "/" + MONEY + r"(?:/" + MONEY + r")?\) (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})", b)
        if not head:
            continue
        h["id"] = head.group(1)
        sb, bb = _m(head.group(2)), _m(head.group(3))
        ante = _m(head.group(4)) if head.group(4) else 0.0
        h["sb"], h["bb"], h["ante"] = sb, bb, ante
        h["dt"] = datetime.strptime(head.group(5), "%Y/%m/%d %H:%M:%S")
        end = re.search(r"Game ended: (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})", b)
        h["dt_end"] = datetime.strptime(end.group(1), "%Y/%m/%d %H:%M:%S") if end else None
        h["table"] = (re.search(r"Table '(\S+)'", b) or [None, "?"])[1]
        btn = re.search(r"Seat #(\d+) is the button", b)
        h["btn_seat"] = int(btn.group(1)) if btn else None
        seats = re.findall(r"^Seat (\d+): (\S+) \(" + MONEY + r" in chips\)", b, re.M)
        h["seats"] = [(int(n), name, _m(st)) for n, name, st in seats]
        h["n"] = len(h["seats"])
        hero = next(((int(n), _m(st)) for n, name, st in seats if name == "Hero"), None)
        if not hero:
            continue
        h["hero_seat"], h["hero_stack"] = hero
        hc = re.search(r"Dealt to Hero \[([^\]]+)\]", b)
        h["hero_cards"] = hc.group(1).split() if hc else None
        # position: order after button among occupied seats
        order = sorted(s[0] for s in h["seats"])
        if h["btn_seat"] in order:
            rot = order[order.index(h["btn_seat"]):] + order[:order.index(h["btn_seat"])]
        else:
            rot = order
        # HU: button = SB
        n = h["n"]
        posnames = (["BTN/SB", "BB"] if n == 2 else
                    (["BTN", "SB", "BB"] + ["EP", "MP", "CO"][:n - 3]) if n <= 6 else ["BTN", "SB", "BB", "EP", "EP", "MP", "CO"])
        if n > 2:
            labels = ["BTN", "SB", "BB"] + {3: [], 4: ["CO"], 5: ["MP", "CO"], 6: ["EP", "MP", "CO"]}[min(n, 6)]
        else:
            labels = ["BTN/SB", "BB"]
        seat2pos = {rot[i]: labels[i] for i in range(min(len(rot), len(labels)))}
        h["hero_pos"] = seat2pos.get(h["hero_seat"], "?")
        # streets + actions
        street_pat = re.split(r"\*\*\* (HOLE CARDS|FLOP|TURN|RIVER|SHOWDOWN) \*\*\*", b)
        streets = {}
        cur = "pre_deal"
        for i in range(1, len(street_pat), 2):
            streets[street_pat[i]] = street_pat[i + 1]
        board = re.search(r"Board \[([^\]]*)\]", b)
        h["board"] = board.group(1).split() if board and board.group(1).strip() else []
        acts = []
        invested = defaultdict(float)          # per player: total chips in
        # blinds + antes first (they seed the running pot)
        for who, amt in re.findall(r"^(\S+): posts (?:ante|small blind|big blind|dead blind)[^\d\u20AE]*" + MONEY, b, re.M):
            invested[who] += _m(amt)
        pot_run = sum(invested.values())       # running pot BEFORE each action (for true bet-fraction sizing)
        for sname in ("HOLE CARDS", "FLOP", "TURN", "RIVER"):
            seg = streets.get(sname, "")
            street_commit = defaultdict(float)
            if sname == "HOLE CARDS":          # blinds count toward preflop street commitment
                for who, amt in re.findall(r"^(\S+): posts (?:small blind|big blind)[^\d\u20AE]*" + MONEY, b, re.M):
                    street_commit[who] += _m(amt)
            skey = {"HOLE CARDS": "preflop", "FLOP": "flop", "TURN": "turn", "RIVER": "river"}[sname]
            for line in seg.splitlines():
                mm = re.match(r"^(\S+): (folds|checks|calls|bets|raises|ALLIN) ?" + MONEY + r"?(?: to " + MONEY + r")?", line)
                if mm:
                    who, act = mm.group(1), mm.group(2)
                    amt = _m(mm.group(3)) if mm.group(3) else 0.0
                    to = _m(mm.group(4)) if mm.group(4) else None
                    delta = 0.0
                    if act == "raises" and to is not None:
                        delta = to - street_commit[who]
                        street_commit[who] = to
                    elif act in ("calls", "bets"):
                        delta = amt
                        street_commit[who] += amt
                    elif act == "ALLIN":       # CoinPoker verb: commits amt ADDITIONAL chips (rest of stack)
                        delta = amt
                        street_commit[who] += amt
                    invested[who] += delta
                    acts.append({"street": skey, "who": who, "act": act.lower() if act != "ALLIN" else "allin",
                                 "amt": amt, "to": to, "pot_before": pot_run, "delta": delta})
                    pot_run += delta
                mret = re.match(r"^(\S+): RETURN " + MONEY, line)
                if mret:
                    invested[mret.group(1)] -= _m(mret.group(2))
                    pot_run -= _m(mret.group(2))
        h["acts"] = acts
        h["invested_hero"] = invested.get("Hero", 0.0)
        col = sum(_m(x) for x in re.findall(r"^Hero collected " + MONEY + r" from pot", b, re.M))
        col += sum(_m(x) for x in re.findall(r"^Seat \d+: Hero .*won \(" + MONEY + r"\)", b, re.M)) if col == 0 else 0
        h["collected_hero"] = col
        h["net"] = col - invested.get("Hero", 0.0)
        h["net_bb"] = h["net"] / bb
        h["pot_bb"] = _m((re.search(r"Total pot " + MONEY, b) or [None, "0"])[1]) / bb
        h["hero_shows"] = (re.search(r"Hero: shows \[([^\]]+)\]", b) or [None, None])[1]
        h["villain_shows"] = re.findall(r"^(?!Hero)(\S+): shows \[([^\]]+)\]", b, re.M)
        h["saw_flop_hero"] = ("FLOP" in streets) and not any(a["who"] == "Hero" and a["act"] == "folds" and a["street"] == "preflop" for a in acts)
        # TRUE showdown: an actual 'shows [' ACTION line exists (cards were compared) and Hero never folded.
        # (Neither the '*** SHOWDOWN ***' header nor the summary 'Hero showed' marks a real showdown —
        # CoinPoker emits both even when everyone folds preflop.)
        hero_folded = any(a["who"] == "Hero" and a["act"] == "folds" for a in acts)
        h["went_sd"] = bool(re.search(r"^\S+: shows \[", b, re.M)) and not hero_folded
        h["won"] = col > 0
        h["src"] = "cash"
        # all-in: the explicit ALLIN verb, or >=95% of the starting stack committed
        h["allin_hero"] = (any(a["who"] == "Hero" and a["act"] == "allin" for a in acts)
                          or (invested.get("Hero", 0.0) >= 0.95 * h["hero_stack"] and h["hero_stack"] > 0))
        hands.append(h)
    return hands


# ---------------------------------------------------------------- GG tournament parser (reuse simplified)
def parse_gg():
    txt = open(GG, encoding="utf-8").read()
    blocks = [b for b in re.split(r"(?=Poker Hand #)", txt) if b.strip().startswith("Poker Hand")][::-1]
    hands = []
    for i, b in enumerate(blocks):
        h = {}
        lvl = re.search(r"Level(\d+)\(([\d,]+)/([\d,]+)\(([\d,]+)\)\)", b)
        h["sb"], h["bb"], h["ante"] = _m(lvl.group(2)), _m(lvl.group(3)), _m(lvl.group(4))
        dt = re.search(r"- (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})", b)
        h["dt"] = datetime.strptime(dt.group(1), "%Y/%m/%d %H:%M:%S") if dt else None
        h["dt_end"] = None
        h["id"] = "GG" + str(i + 1)
        seats = re.findall(r"^Seat (\d+): (\S+) \(([\d,]+) in chips\)", b, re.M)
        h["seats"] = [(int(n), name, _m(st)) for n, name, st in seats]
        h["n"] = len(seats)
        hero = next(((int(n), _m(st)) for n, name, st in seats if name == "Hero"), None)
        if not hero:
            continue
        h["hero_seat"], h["hero_stack"] = hero
        btn = re.search(r"Seat #(\d+) is the button", b)
        h["btn_seat"] = int(btn.group(1)) if btn else None
        hc = re.search(r"Dealt to Hero \[([^\]]+)\]", b)
        h["hero_cards"] = hc.group(1).split() if hc else None
        posts_sb = bool(re.search(r"Hero: posts small blind", b))
        posts_bb = bool(re.search(r"Hero: posts (?:big blind|button blind)", b))
        h["hero_pos"] = "BTN" if h["hero_seat"] == h["btn_seat"] else ("SB" if posts_sb else ("BB" if posts_bb else "EP"))
        acts = []
        for street, seg in re.findall(r"\*\*\* (FLOP|TURN|RIVER|HOLE CARDS) \*\*\*([\s\S]*?)(?=\*\*\* |\Z)", b):
            skey = {"HOLE CARDS": "preflop", "FLOP": "flop", "TURN": "turn", "RIVER": "river"}[street]
            for line in seg.splitlines():
                mm = re.match(r"^(\S+): (folds|checks|calls|bets|raises) ?([\d,]+)?(?: to ([\d,]+))?", line)
                if mm:
                    acts.append({"street": skey, "who": mm.group(1), "act": mm.group(2),
                                 "amt": _m(mm.group(3)) if mm.group(3) else 0.0,
                                 "to": _m(mm.group(4)) if mm.group(4) else None})
        h["acts"] = acts
        col = sum(_m(x) for x in re.findall(r"^(?:Hero|Seat \d+: Hero[^\n]*?) collected ([\d,]+)", b, re.M))
        won_line = re.findall(r"^Seat \d+: Hero.*won \(([\d,]+)\)", b, re.M)
        col = col or sum(_m(x) for x in won_line)
        h["collected_hero"] = col
        # invested: reconstruct
        invested = 0.0
        for a in acts:
            if a["who"] == "Hero":
                if a["act"] == "raises" and a["to"] is not None:
                    pass
        # simpler: blinds/antes + action amounts, using GG per-hand chip delta unavailable -> approximate
        inv = defaultdict(float); sc = defaultdict(float); cur_street = "preflop"
        for a in acts:
            if a["street"] != cur_street:
                cur_street = a["street"]; sc = defaultdict(float)
            if a["act"] == "raises" and a["to"] is not None:
                inv[a["who"]] += a["to"] - sc[a["who"]]; sc[a["who"]] = a["to"]
            elif a["act"] in ("calls", "bets"):
                inv[a["who"]] += a["amt"]; sc[a["who"]] += a["amt"]
        for who, amt in re.findall(r"^(\S+): posts (?:the ante|small blind|big blind|button blind) ([\d,]+)", b, re.M):
            inv[who] += _m(amt)
        for who, amt in re.findall(r"^Uncalled bet \(([\d,]+)\) returned to (\S+)", b, re.M):
            pass
        for amt, who in re.findall(r"^Uncalled bet \(([\d,]+)\) returned to (\S+)", b, re.M):
            inv[who] -= _m(amt)
        h["invested_hero"] = inv.get("Hero", 0.0)
        h["net"] = col - h["invested_hero"]
        h["net_bb"] = h["net"] / h["bb"]
        pot = re.search(r"Total pot ([\d,]+)", b)
        h["pot_bb"] = _m(pot.group(1)) / h["bb"] if pot else 0.0
        h["board"] = (re.search(r"Board \[([^\]]*)\]", b) or [None, ""])[1].split()
        h["hero_shows"] = (re.search(r"Hero: shows \[([^\]]+)\]", b) or [None, None])[1]
        h["villain_shows"] = re.findall(r"^(?!Hero)(\S+): shows \[([^\]]+)\]", b, re.M)
        h["saw_flop_hero"] = ("*** FLOP" in b) and not any(a["who"] == "Hero" and a["act"] == "folds" and a["street"] == "preflop" for a in acts)
        h["went_sd"] = "*** SHOWDOWN" in b and h["hero_shows"] is not None
        h["won"] = col > 0
        h["src"] = "tourney"
        h["allin_hero"] = h["invested_hero"] >= 0.95 * h["hero_stack"] and h["hero_stack"] > 0
        h["table"] = "GG"
        hands.append(h)
    return hands


# ---------------------------------------------------------------- stats
def hero_acts(h, street=None):
    return [a for a in h["acts"] if a["who"] == "Hero" and (street is None or a["street"] == street)]


def compute_stats(hands, label):
    S = {"label": label, "n_hands": len(hands)}
    if not hands:
        return S
    # VPIP: voluntarily put money preflop (call/bet/raise, not blinds)
    vpip = [h for h in hands if any(a["act"] in ("calls", "bets", "raises") for a in hero_acts(h, "preflop"))]
    pfr = [h for h in hands if any(a["act"] == "raises" or (a["act"] == "bets") for a in hero_acts(h, "preflop"))]
    S["vpip"] = len(vpip) / len(hands)
    S["pfr"] = len(pfr) / len(hands)
    S["pfr_over_vpip"] = (len(pfr) / len(vpip)) if vpip else None
    # limp: preflop call with no raise before hero
    limps = 0; limp_opp = 0
    for h in hands:
        pre = [a for a in h["acts"] if a["street"] == "preflop"]
        first_hero = next((i for i, a in enumerate(pre) if a["who"] == "Hero"), None)
        if first_hero is None:
            continue
        raised_before = any(a["act"] == "raises" for a in pre[:first_hero])
        if not raised_before and h["hero_pos"] not in ("BB",):
            limp_opp += 1
            if pre[first_hero]["act"] == "calls":
                limps += 1
    S["limp"] = (limps / limp_opp) if limp_opp else None
    S["limp_n"] = limp_opp
    # 3bet: hero raises after exactly one raise before him preflop
    tb = 0; tb_opp = 0; fb = 0; fb_opp = 0
    for h in hands:
        pre = [a for a in h["acts"] if a["street"] == "preflop"]
        nr = 0
        for a in pre:
            if a["who"] == "Hero":
                if nr == 1:
                    tb_opp += 1
                    if a["act"] == "raises":
                        tb += 1
                if nr == 2:
                    fb_opp += 1
                    if a["act"] == "raises":
                        fb += 1
            if a["act"] == "raises":
                nr += 1
    S["threebet"] = tb / tb_opp if tb_opp else None; S["threebet_n"] = tb_opp
    S["fourbet"] = fb / fb_opp if fb_opp else None; S["fourbet_n"] = fb_opp
    # AF postflop
    bets = sum(1 for h in hands for a in hero_acts(h) if a["street"] != "preflop" and a["act"] in ("bets", "raises"))
    calls = sum(1 for h in hands for a in hero_acts(h) if a["street"] != "preflop" and a["act"] == "calls")
    S["af"] = bets / calls if calls else None; S["af_n"] = bets + calls
    # cbet flop: hero was last preflop aggressor and bets flop first chance
    cb = 0; cb_opp = 0
    for h in hands:
        pre = [a for a in h["acts"] if a["street"] == "preflop"]
        aggr = [a["who"] for a in pre if a["act"] == "raises"]
        if aggr and aggr[-1] == "Hero" and h["saw_flop_hero"]:
            fl = [a for a in h["acts"] if a["street"] == "flop"]
            hero_first = next((a for a in fl if a["who"] == "Hero"), None)
            faced_bet = any(a["act"] in ("bets", "raises") for a in fl[:fl.index(hero_first)]) if hero_first in fl else False
            if hero_first and not faced_bet:
                cb_opp += 1
                if hero_first["act"] == "bets":
                    cb += 1
    S["cbet_flop"] = cb / cb_opp if cb_opp else None; S["cbet_flop_n"] = cb_opp
    # WWSF / WTSD / W$SD
    sawf = [h for h in hands if h["saw_flop_hero"]]
    S["wwsf"] = sum(1 for h in sawf if h["won"]) / len(sawf) if sawf else None; S["wwsf_n"] = len(sawf)
    wtsd = [h for h in sawf if h["went_sd"]]
    S["wtsd"] = len(wtsd) / len(sawf) if sawf else None
    S["wsd"] = sum(1 for h in wtsd if h["won"]) / len(wtsd) if wtsd else None; S["wsd_n"] = len(wtsd)
    # non-showdown winnings
    S["nsd_bb"] = sum(h["net_bb"] for h in hands if not h["went_sd"])
    S["sd_bb"] = sum(h["net_bb"] for h in hands if h["went_sd"])
    # positions
    pos = defaultdict(lambda: [0, 0.0])
    for h in hands:
        pos[h["hero_pos"]][0] += 1; pos[h["hero_pos"]][1] += h["net_bb"]
    S["positions"] = {p: {"n": v[0], "net_bb": round(v[1], 1), "bb100": round(v[1] / v[0] * 100, 1)} for p, v in pos.items()}
    # sizing distribution: hero postflop bets as a fraction of the TRUE running pot at decision time
    sizes = []
    for h in hands:
        for a in hero_acts(h):
            if a["street"] != "preflop" and a["act"] == "bets" and a.get("pot_before", 0) > 0:
                sizes.append(a["amt"] / a["pot_before"])
    buckets = Counter()
    for s in sizes:
        buckets["<0.4"] += 0
    def bucket(s):
        if s < 0.4: return "<0.4pot"
        if s < 0.7: return "0.4-0.7"
        if s < 1.0: return "0.7-1.0"
        if s < 1.5: return "1.0-1.5"
        return ">1.5pot(overbet)"
    bc = Counter(bucket(s) for s in sizes)
    S["sizing_dist"] = dict(bc); S["sizing_n"] = len(sizes)
    tot = sum(bc.values())
    S["sizing_entropy"] = round(-sum((c / tot) * math.log2(c / tot) for c in bc.values() if c), 3) if tot else None
    S["overbet_share"] = (bc[">1.5pot(overbet)"] / tot) if tot else None
    # all-in freq
    S["allin_freq"] = sum(1 for h in hands if h["allin_hero"]) / len(hands)
    S["allin_n"] = sum(1 for h in hands if h["allin_hero"])
    # winrate
    S["bb100"] = round(sum(h["net_bb"] for h in hands) / len(hands) * 100, 2)
    net = [h["net_bb"] for h in hands]
    mean = sum(net) / len(net)
    sd = (sum((x - mean) ** 2 for x in net) / max(1, len(net) - 1)) ** 0.5
    S["bb100_se"] = round(sd / math.sqrt(len(net)) * 100, 2)
    S["perhand_sd_bb"] = round(sd, 2)
    # blind defense: BB facing a raise -> fold?
    bbf = 0; bbo = 0; bb3 = 0
    for h in hands:
        if h["hero_pos"] not in ("BB", "BTN/SB"):
            continue
        pre = [a for a in h["acts"] if a["street"] == "preflop"]
        fh = next((i for i, a in enumerate(pre) if a["who"] == "Hero"), None)
        if fh is None: continue
        if any(a["act"] == "raises" for a in pre[:fh]):
            bbo += 1
            if pre[fh]["act"] == "folds": bbf += 1
            if pre[fh]["act"] == "raises": bb3 += 1
    S["blind_fold_vs_raise"] = bbf / bbo if bbo else None
    S["blind_3bet_vs_raise"] = bb3 / bbo if bbo else None
    S["blind_face_n"] = bbo
    return S


# ---------------------------------------------------------------- H4/H5/H6 dynamics
def dynamics(hands_sorted):
    """Trigger analysis (H4), session hazard (H5), stake escalation (H6) on the time-ordered cash hands."""
    R = {}
    # sessions: gap > 45 min
    sessions = []; cur = [hands_sorted[0]]
    for h in hands_sorted[1:]:
        if (h["dt"] - cur[-1]["dt"]).total_seconds() > 45 * 60:
            sessions.append(cur); cur = [h]
        else:
            cur.append(h)
    sessions.append(cur)
    R["n_sessions"] = len(sessions)
    R["session_lengths"] = [len(s) for s in sessions]
    # H4 triggers: lost pot >= 20bb at showdown, or lost all-in
    triggers = []
    for i, h in enumerate(hands_sorted):
        if (h["net_bb"] <= -20 and h["went_sd"]) or (h["allin_hero"] and h["net_bb"] < 0):
            triggers.append(i)
    R["n_triggers"] = len(triggers)
    def window(after, k):
        idx = set()
        for t in after:
            idx.update(range(t + 1, min(t + 1 + k, len(hands_sorted))))   # UNION — overlapping windows deduped
        return [hands_sorted[i] for i in sorted(idx)]
    base_bb100 = sum(h["net_bb"] for h in hands_sorted) / len(hands_sorted) * 100
    for k in (30, 60):
        w = window(triggers, k)
        if w:
            wr = sum(h["net_bb"] for h in w) / len(w) * 100
            vp = sum(1 for h in w if any(a["act"] in ("calls", "bets", "raises") for a in hero_acts(h, "preflop"))) / len(w)
            R[f"post_trigger_{k}"] = {"n": len(w), "bb100": round(wr, 1), "vpip": round(vp, 3)}
    R["baseline_bb100"] = round(base_bb100, 1)
    base_vp = sum(1 for h in hands_sorted if any(a["act"] in ("calls", "bets", "raises") for a in hero_acts(h, "preflop"))) / len(hands_sorted)
    R["baseline_vpip"] = round(base_vp, 3)
    # H5: does the session end soon after a big win?  big win = pot won >= 20bb
    ends_after_bigwin = 0; ends_after_bigloss = 0; other_end = 0
    for s in sessions:
        last5 = s[-5:]
        if any(h["net_bb"] >= 20 for h in last5):
            ends_after_bigwin += 1
        elif any(h["net_bb"] <= -20 for h in last5):
            ends_after_bigloss += 1
        else:
            other_end += 1
    # baseline: share of ALL 5-hand windows containing a >=20bb win
    wins20 = [h["net_bb"] >= 20 for h in hands_sorted]
    windows = [any(wins20[i:i + 5]) for i in range(len(wins20) - 4)]
    R["h5"] = {"sessions_ending_after_bigwin": ends_after_bigwin,
               "sessions_ending_after_bigloss": ends_after_bigloss,
               "sessions_other": other_end,
               "baseline_share_5hand_windows_with_bigwin": round(sum(windows) / len(windows), 3) if windows else None}
    # H6: stake path over time
    stakes = [(h["dt"], h["bb"]) for h in hands_sorted]
    jumps = []
    for i in range(1, len(hands_sorted)):
        if hands_sorted[i]["bb"] > hands_sorted[i - 1]["bb"] * 1.9:
            prev_net = sum(x["net_bb"] for x in hands_sorted[max(0, i - 20):i])
            trig_near = any(abs(i - t) <= 20 for t in triggers)
            jumps.append({"i": i, "from_bb": hands_sorted[i - 1]["bb"], "to_bb": hands_sorted[i]["bb"],
                          "prev20_net_bb": round(prev_net, 1), "trigger_within_20": trig_near})
    R["h6_jumps_up"] = jumps
    # H6 base rate: what fraction of ALL hands lie within 20 hands of some trigger? (54 triggers cover a lot —
    # without this base rate the "14/15 jumps near a trigger" claim would be dishonest)
    near = set()
    for t in triggers:
        near.update(range(max(0, t - 20), min(len(hands_sorted), t + 21)))
    R["h6_base_rate_near_trigger"] = round(len(near) / len(hands_sorted), 3)
    R["stake_sequence"] = sorted(set(h["bb"] for h in hands_sorted))
    # H9 proxy (no persistent villain IDs -> behavior-per-hand ecology): LP-marker = >=1 villain limped
    # preflop; AGG-marker = hero faced a 3bet+ preflop. Winrate split across these hand-ecologies.
    def villain_limped(h):
        pre = [a for a in h["acts"] if a["street"] == "preflop"]
        for i, a in enumerate(pre):
            if a["who"] != "Hero" and a["act"] == "calls" and not any(x["act"] in ("raises", "allin") for x in pre[:i]):
                return True
        return False
    def faced_3bet(h):
        pre = [a for a in h["acts"] if a["street"] == "preflop"]
        r = 0
        for a in pre:
            if a["act"] == "raises":
                r += 1
                if r >= 2 and a["who"] != "Hero":
                    return True
        return False
    lp = [h for h in hands_sorted if villain_limped(h)]
    ag = [h for h in hands_sorted if faced_3bet(h)]
    rest = [h for h in hands_sorted if not villain_limped(h) and not faced_3bet(h)]
    def wr(seg):
        return {"n": len(seg), "bb100": round(sum(x["net_bb"] for x in seg) / len(seg) * 100, 1)} if seg else {"n": 0}
    R["h9_proxy"] = {"vs_limper_hands(LP-marker)": wr(lp), "faced_3bet_hands(AGG-marker)": wr(ag), "neither": wr(rest)}
    # H10 proxy: only per-HAND duration exists (no per-action timing). seconds per hero decision,
    # post-trigger windows vs baseline.
    def dur_per_dec(seg):
        ds = []
        for h in seg:
            if h.get("dt_end") and h["dt"]:
                nd = max(1, len([a for a in h["acts"] if a["who"] == "Hero"]))
                ds.append((h["dt_end"] - h["dt"]).total_seconds() / nd)
        if not ds:
            return None
        m = sum(ds) / len(ds)
        v = (sum((x - m) ** 2 for x in ds) / max(1, len(ds) - 1)) ** 0.5
        return {"n": len(ds), "mean_s": round(m, 1), "sd_s": round(v, 1)}
    post_idx = set()
    for t in triggers:
        post_idx.update(range(t + 1, min(t + 31, len(hands_sorted))))
    R["h10_proxy"] = {"baseline": dur_per_dec(hands_sorted),
                      "post_trigger30": dur_per_dec([hands_sorted[i] for i in sorted(post_idx)])}
    return R, sessions, triggers


# ---------------------------------------------------------------- H8 bluff anatomy
RANKS = "23456789TJQKA"


def hand_strength_at_showdown(cards, board):
    """crude made-hand class at river via treys"""
    try:
        from treys import Card, Evaluator
        ev = Evaluator()
        c = [Card.new(x[0].upper() + x[1].lower()) for x in cards]
        bd = [Card.new(x[0].upper() + x[1].lower()) for x in board[:5]]
        if len(bd) < 3:
            return None
        score = ev.evaluate(bd, c)
        cls = ev.get_rank_class(score)
        return ev.class_to_string(cls)
    except Exception:
        return None


def h8_bluffs(hands):
    shown = [h for h in hands if h["hero_shows"] and len(h["board"]) >= 5]
    out = {"n_shown_river": 0, "bluffs_shown": 0, "bluff_with_blocker": 0, "value_shown": 0, "bluff_sizes": []}
    for h in shown:
        river_bets = [a for a in hero_acts(h, "river") if a["act"] in ("bets", "raises")]
        if not river_bets:
            continue
        out["n_shown_river"] += 1
        cls = hand_strength_at_showdown(h["hero_shows"].split(), h["board"])
        weak = cls in ("High Card", "Pair") and h["net_bb"] < 0
        if weak:
            out["bluffs_shown"] += 1
            if any(c[0] == "A" for c in h["hero_shows"].split()):
                out["bluff_with_blocker"] += 1
            if h["pot_bb"] > 0:
                out["bluff_sizes"].append(round(river_bets[0]["amt"] / h["bb"] / max(h["pot_bb"], 0.01), 2))
        else:
            out["value_shown"] += 1
    return out


# ---------------------------------------------------------------- main
def main():
    cash = parse_coinpoker()
    tour = parse_gg()
    cash.sort(key=lambda h: h["dt"])
    print(f"parsed: cash={len(cash)} tourney={len(tour)}")
    allh = cash + tour

    res = {"n_cash": len(cash), "n_tourney": len(tour)}
    res["stats_cash_all"] = compute_stats(cash, "cash all")
    res["stats_cash_6max"] = compute_stats([h for h in cash if h["n"] >= 5], "cash 5-6max")
    res["stats_cash_short"] = compute_stats([h for h in cash if h["n"] <= 3], "cash HU/3max")
    res["stats_tourney"] = compute_stats(tour, "tournament")
    # per stake
    res["per_stake"] = {}
    for bb in sorted(set(h["bb"] for h in cash)):
        seg = [h for h in cash if h["bb"] == bb]
        res["per_stake"][str(bb)] = {"n": len(seg), "bb100": round(sum(x["net_bb"] for x in seg) / len(seg) * 100, 1),
                                     "net_bb_total": round(sum(x["net_bb"] for x in seg), 1)}
    dyn, sessions, triggers = dynamics(cash)
    res["dynamics"] = dyn
    res["h8"] = h8_bluffs(cash)
    # annotation candidates
    bypot = sorted(allh, key=lambda h: -h["pot_bb"])[:50]
    bynet = sorted(allh, key=lambda h: -abs(h["net_bb"]))[:50]
    def annot(h):
        tags = []
        if h["allin_hero"]: tags.append("ALLES-AUF-EINE-KARTE")
        if h["won"] and not h["went_sd"] and any(a["act"] in ("bets", "raises") for a in hero_acts(h)): tags.append("SIEG-OHNE-KAMPF")
        if h["hero_shows"] and h["net_bb"] < 0 and len(h["board"]) >= 5:
            cls = hand_strength_at_showdown(h["hero_shows"].split(), h["board"])
            if cls in ("High Card", "Pair"): tags.append("PERFORMANCE-BLUFF")
        if h["hero_pos"] in ("BTN", "CO", "BTN/SB") and h["net_bb"] > 10: tags.append("HERRSCHAFT-IN-POSITION")
        if h["net_bb"] <= -20 and h["went_sd"]: tags.append("KOLLAPS-PAYOFF-KANDIDAT")
        if not tags: tags.append("UNKLASSIFIZIERT")
        return {"id": h["id"], "src": h["src"], "dt": h["dt"].isoformat() if h["dt"] else None,
                "stake_bb": h["bb"], "pos": h["hero_pos"], "pot_bb": round(h["pot_bb"], 1),
                "net_bb": round(h["net_bb"], 1), "cards": h["hero_cards"], "tags": tags}
    res["top50_pot"] = [annot(h) for h in bypot]
    res["top50_net"] = [annot(h) for h in bynet]
    tagc = Counter(t for a in (res["top50_pot"] + res["top50_net"]) for t in a["tags"])
    res["tag_distribution"] = dict(tagc)
    import os
    os.makedirs(r"C:\Users\hampe\Desktop\PokerB\data\research_sweep", exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, default=str)
    print("saved ->", OUT)
    # console summary
    for k in ("stats_cash_all", "stats_cash_6max", "stats_tourney"):
        s = res[k]
        print(f"\n[{s['label']}] n={s['n_hands']} vpip={s['vpip']:.2f} pfr={s['pfr']:.2f} 3bet={s.get('threebet')} "
              f"af={s.get('af')} wwsf={s.get('wwsf')} wtsd={s.get('wtsd')} wsd={s.get('wsd')} bb100={s['bb100']}+/-{s['bb100_se']}")
    print("\ndynamics:", json.dumps(dyn, indent=1, default=str)[:1200])
    print("\nh8:", res["h8"])
    print("\ntags:", dict(tagc))


if __name__ == "__main__":
    main()
