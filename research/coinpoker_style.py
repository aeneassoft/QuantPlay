# -*- coding: utf-8 -*-
"""Parse a CoinPoker cash hand-history export (Hero = the user) and profile the PLAYER'S STYLE:
VPIP / PFR / 3bet / open-limp / c-bet / WTSD / aggression / bet-sizing / by-position — the stuff that
shows HOW someone plays (unusual approaches), not just GTO leaks.

  python research/coinpoker_style.py "C:/Users/hampe/Desktop/CoinPoker_..._Cash.txt"
"""
import re
import sys
from collections import defaultdict, Counter

AMT = re.compile(r"₮([\d,]+(?:\.\d+)?)")


def amt(s):
    m = AMT.search(s)
    return float(m.group(1).replace(",", "")) if m else 0.0


def split_hands(text):
    out, cur = [], []
    for line in text.splitlines():
        if line.startswith("CoinPoker Hand #"):
            if cur:
                out.append(cur)
            cur = [line]
        elif cur:
            cur.append(line)
    if cur:
        out.append(cur)
    return out


def positions(active, button):
    """active=sorted seat ints, button=seat int -> {seat: POSNAME}."""
    if button not in active:
        button = active[0]
    bi = active.index(button)
    rot = active[bi:] + active[:bi]          # BTN, SB, BB, ...
    n = len(rot)
    names = {}
    base = {0: "BTN", 1: "SB", 2: "BB"} if n > 2 else {0: "BTN/SB", 1: "BB"}
    for off, seat in enumerate(rot):
        if off in base:
            names[seat] = base[off]
        elif off == n - 1:
            names[seat] = "CO"
        elif off == n - 2:
            names[seat] = "HJ"
        else:
            names[seat] = "UTG"
    return names


def analyze(text, minbb=0.0):
    hands = split_hands(text)
    bb = 20.0
    st = dict(n=0, dealt=0, vpip=0, pfr=0, limp=0,
              tb_opp=0, tb=0,                       # 3bet opportunities / 3bets
              flop_seen=0, cbet_opp=0, cbet=0, wtsd=0, won_sd=0,
              postflop_bet=0, postflop_raise=0, postflop_call=0,
              net=0.0, net_bb=0.0)
    sizes = []                                       # postflop bet fractions of pot
    by_pos = defaultdict(lambda: dict(n=0, vpip=0, pfr=0))
    bb100_by_pos = defaultdict(float)

    for h in hands:
        text_h = "\n".join(h)
        if "Dealt to Hero [" not in text_h:
            continue                                 # Hero not dealt a known hand (sitting out)
        m_bb = re.search(r"NLH \(₮[\d,.]+/₮([\d,.]+)", text_h)   # per-hand BB (file spans micro→mid)
        hand_bb = float(m_bb.group(1).replace(",", "")) if m_bb else 20.0
        if hand_bb < minbb:                          # focus the read on meaningful stakes
            continue
        st["n"] += 1; st["dealt"] += 1
        # seats + button
        seats = {}
        for ln in h:
            m = re.match(r"Seat (\d+): (.+?) \(₮[\d,.]+ in chips\)", ln)   # decl line only (NOT summary "won (₮)")
            if m:
                seats[int(m.group(1))] = m.group(2)
        bmatch = re.search(r"Seat #(\d+) is the button", text_h)
        button = int(bmatch.group(1)) if bmatch else min(seats)
        active = sorted(seats)
        pos = positions(active, button)
        hero_seat = next((s for s, nm in seats.items() if nm == "Hero"), None)
        hpos = pos.get(hero_seat, "?")
        if hpos == "?":
            st["nopos"] = st.get("nopos", 0) + 1
            if st["nopos"] <= 2:
                sys.stderr.write(f"DBG ?  seats={seats}  btn={button}  hero_seat={hero_seat}  "
                                 f"hdr={h[0][:40]!r}\n")
        by_pos[hpos]["n"] += 1

        # street boundaries
        def idx(tag):
            for i, ln in enumerate(h):
                if ln.startswith(tag):
                    return i
            return None
        i_hole = idx("*** HOLE CARDS ***")
        i_flop = idx("*** FLOP ***")
        i_turn = idx("*** TURN ***")
        i_river = idx("*** RIVER ***")
        i_show = idx("*** SHOW")
        i_summ = idx("*** SUMMARY ***")
        pf_end = i_flop or i_show or i_summ or len(h)

        # ---- preflop ----
        raises_before = 0
        hero_vpip = hero_pfr = hero_limp = hero_3bet = False
        faced_open = False
        for ln in h[(i_hole or 0) + 1:pf_end]:
            who_raise = re.match(r"(.+?): raises ", ln)
            who_call = re.match(r"(.+?): calls ", ln)
            is_hero = ln.startswith("Hero:")
            if is_hero and "raises" in ln:
                hero_vpip = hero_pfr = True
                if raises_before >= 1:
                    hero_3bet = True
            elif is_hero and "calls" in ln:
                hero_vpip = True
                if raises_before == 0:
                    hero_limp = True
            # 3bet opportunity: Hero faced exactly one open before acting (first decision)
            if not is_hero and "raises" in ln and not hero_vpip and raises_before == 0:
                faced_open = True
            if who_raise:
                raises_before += 1
        st["vpip"] += hero_vpip; st["pfr"] += hero_pfr; st["limp"] += hero_limp
        if faced_open:
            st["tb_opp"] += 1
            st["tb"] += hero_3bet
        by_pos[hpos]["vpip"] += hero_vpip; by_pos[hpos]["pfr"] += hero_pfr

        # ---- postflop ----
        saw_flop = i_flop is not None
        if saw_flop:
            st["flop_seen"] += 1
            # pot at flop start ≈ sum of all preflop contributions; approximate via "Total pot" fallback
            pot_running = 0.0
            for ln in h[(i_hole or 0) + 1:pf_end]:
                if any(k in ln for k in ("posts ante", "posts small blind", "posts big blind", "calls", "raises ", "bets ")):
                    pot_running += amt(ln) if "raises" not in ln else amt(ln)  # increment for raises
            # Hero is PFR if last preflop aggressor
            last_pf_raiser = None
            for ln in h[(i_hole or 0) + 1:pf_end]:
                if "raises" in ln:
                    last_pf_raiser = ln.split(":")[0]
            hero_pfr_postflop = (last_pf_raiser == "Hero")
            # flop: did Hero get a c-bet chance + take it
            flop_lines = h[i_flop + 1:(i_turn or i_show or i_summ or len(h))]
            if hero_pfr_postflop:
                st["cbet_opp"] += 1
                if any(ln.startswith("Hero:") and "bets" in ln for ln in flop_lines):
                    st["cbet"] += 1
            # postflop aggression + bet sizes (flop/turn/river)
            post = h[i_flop + 1:(i_summ or len(h))]
            run_pot = pot_running
            for ln in post:
                if ln.startswith("*** "):
                    continue
                a = amt(ln)
                if ln.startswith("Hero:"):
                    if "bets" in ln:
                        st["postflop_bet"] += 1
                        if run_pot > 0:
                            sizes.append(round(a / run_pot, 2))
                    elif "raises" in ln:
                        st["postflop_raise"] += 1
                    elif "calls" in ln:
                        st["postflop_call"] += 1
                # track pot growth (rough)
                if any(k in ln for k in ("bets", "calls", "raises")):
                    run_pot += a
            # showdown
            if i_show is not None:
                st["wtsd"] += 1
                if re.search(r"Hero (showed|mucked).*won|Hero collected", text_h) or \
                   re.search(r"Seat \d+: Hero.*won", text_h):
                    st["won_sd"] += 1

        # ---- net (bb) ----
        invested = 0.0
        for ln in h:
            if ln.startswith("Hero:"):
                if any(k in ln for k in ("posts ante", "posts small blind", "posts big blind", "calls", "bets")):
                    invested += amt(ln)
                elif "raises" in ln:
                    invested += amt(ln)                  # increment
                elif "RETURN" in ln:
                    invested -= amt(ln)
        collected = 0.0
        for ln in h:
            if "Hero collected" in ln:          # pot Hero scooped (fold-win OR showdown); summary "won" is a DUP
                collected += amt(ln)
        net = collected - invested
        st["net"] += net
        st["net_bb"] += net / hand_bb
        bb100_by_pos[hpos] += net          # ₮ chips per position (mixed stakes → report money, not bb)

    return st, sizes, by_pos, bb100_by_pos


def pct(a, b):
    return f"{100*a/b:.1f}%" if b else "-"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\hampe\Desktop\CoinPoker_Princedarkness_2026-02-01_to_2026-06-28_Cash.txt"
    minbb = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    text = open(path, encoding="utf-8").read()
    st, sizes, by_pos, bb100p = analyze(text, minbb)
    n = st["n"]
    print(f"=== CoinPoker STYLE — Hero, {n} hands (6-max, BB>=₮{minbb:g}) ===\n")
    print(f"Net: +₮{st['net']:.0f} over {n} hands (SMALL sample, mixed stakes → no single clean bb/100).\n")
    print(f"VPIP {pct(st['vpip'],n)}   PFR {pct(st['pfr'],n)}   "
          f"(VPIP-PFR gap {100*(st['vpip']-st['pfr'])/n:.1f}pts)")
    print(f"3-bet {pct(st['tb'],st['tb_opp'])} (of {st['tb_opp']} open-facing)   "
          f"open-LIMP {pct(st['limp'],n)} ({st['limp']} hands)")
    print(f"Flop c-bet {pct(st['cbet'],st['cbet_opp'])} (of {st['cbet_opp']} as PFR)")
    af_calls = max(1, st["postflop_call"])
    print(f"Postflop aggression: bets {st['postflop_bet']} + raises {st['postflop_raise']} vs calls {st['postflop_call']}  "
          f"(AF {(st['postflop_bet']+st['postflop_raise'])/af_calls:.2f})")
    print("\nBy position (n / VPIP / PFR / bb-net):")
    order = ["UTG", "HJ", "CO", "BTN", "SB", "BB", "BTN/SB", "?"]
    for p in order:
        if p in by_pos and by_pos[p]["n"]:
            d = by_pos[p]
            print(f"  {p:6} n={d['n']:4}  VPIP {pct(d['vpip'],d['n']):>6}  PFR {pct(d['pfr'],d['n']):>6}  "
                  f"net {bb100p[p]:+.0f}₮")


if __name__ == "__main__":
    main()
