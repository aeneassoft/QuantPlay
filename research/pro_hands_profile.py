"""Tendency profile of a professional player from raw PokerStars-format hand histories.

CLEAN BOUNDARY: this is an EXPLOIT / VALIDATION reference only (how a strong human plays) — NEVER a training label
and NEVER a cash-game range source. The supplied hands (danic1994) are NLHE **7-max PKO bounty MTT** (antes +
progressive knockouts + ICM) — so the ranges/sizings are tournament/bounty-distorted and do NOT transfer to our HU/
6-max cash bot's ranges. What IS transferable is META-tendency (aggression shape, barrel/showdown frequencies, 3bet
propensity) = an opponent-archetype reference for the exploit engine. Heavy caveats apply; see the printed notes.

Run: python -m extraction.pro_hands_profile [hero=DaniC1994] [glob_dir]
"""
from __future__ import annotations

import glob
import os
import re
import sys

DEF_DIR = ("knowledge_base/hand_histories/players - handhistories/Coin Poker/"
           "MTT - danic1994_98529ivgsk52")


def _hand_blocks(text):
    """Split a file into individual hand blocks (each starts with 'PokerStars Hand #')."""
    parts = re.split(r"(?=PokerStars Hand #)", text)
    return [p for p in parts if p.strip().startswith("PokerStars Hand #")]


def _streets(block):
    """Return (preflop_text, postflop_text, showdown_text) slices of a hand block."""
    hc = block.find("*** HOLE CARDS ***")
    flop = block.find("*** FLOP ***")
    sd = block.find("*** SHOW DOWN ***")
    summ = block.find("*** SUMMARY ***")
    pre = block[hc:flop if flop > 0 else (summ if summ > 0 else len(block))]
    post_end = sd if sd > 0 else (summ if summ > 0 else len(block))
    post = block[flop:post_end] if flop > 0 else ""
    show = block[sd:summ if summ > 0 else len(block)] if sd > 0 else ""
    return pre, post, show


def profile(hero, files):
    n_dealt = 0          # hands hero was seated + dealt
    vpip = pfr = 0       # voluntarily put $ in / raised preflop
    threebet = threebet_opp = 0  # hero 3bet / hero faced an open and could 3bet
    saw_flop = wtsd = wsd = sd_reached = 0
    p_bets = p_raises = p_calls = p_checks = p_folds = 0  # postflop action counts
    bet_to_pot = []      # crude bet-size sampling skipped (pot reconstruction is noisy in MTT antes)

    for fp in files:
        text = open(fp, encoding="utf-8", errors="ignore").read()
        for b in _hand_blocks(text):
            if not re.search(rf"^Seat \d+: {re.escape(hero)} ", b, re.M):
                continue
            n_dealt += 1
            pre, post, show = _streets(b)

            # --- preflop ---
            hero_pre = re.findall(rf"^{re.escape(hero)}: (raises|calls|bets|checks|folds)", pre, re.M)
            # count raises by ANYONE before hero's FIRST raise -> distinguishes open (RFI) vs 3bet+
            pre_lines = pre.splitlines()
            seen_raise = 0
            hero_acted_raise = False
            faced_open = False
            for ln in pre_lines:
                m = re.match(r"^([^:]+): (raises|calls|bets|checks|folds)", ln)
                if not m:
                    continue
                who, act = m.group(1), m.group(2)
                if who == hero:
                    if seen_raise >= 1:
                        faced_open = True          # there was already an open before hero acted
                    if act == "raises":
                        if seen_raise >= 1 and not hero_acted_raise:
                            threebet += 1          # hero re-raised an open = 3bet+
                        hero_acted_raise = True
                    break                          # only hero's first voluntary decision matters here
                if act == "raises":
                    seen_raise += 1
            if faced_open:
                threebet_opp += 1
            if any(a in ("raises", "calls", "bets") for a in hero_pre):
                vpip += 1
            if "raises" in hero_pre:
                pfr += 1

            # --- postflop ACTION counts (hero's own action lines only) ---
            if post:
                for act in re.findall(rf"^{re.escape(hero)}: (bets|raises|calls|checks|folds)", post, re.M):
                    if act == "bets":
                        p_bets += 1
                    elif act == "raises":
                        p_raises += 1
                    elif act == "calls":
                        p_calls += 1
                    elif act == "checks":
                        p_checks += 1
                    elif act == "folds":
                        p_folds += 1
            # --- disposition from SUMMARY (CANONICAL: where hero exited + showdown). The SHOW DOWN section only
            # prints the winner's 'shows' (losers muck silently) -> use the per-seat SUMMARY line instead. ---
            summ = b[b.find("*** SUMMARY ***"):]
            mdisp = re.search(rf"^Seat \d+: {re.escape(hero)}\b(.*)$", summ, re.M)
            disp = mdisp.group(1) if mdisp else ""
            flop_exists = "*** FLOP ***" in b
            if flop_exists and disp and "folded before Flop" not in disp:
                saw_flop += 1
            if ("showed" in disp) or ("mucked" in disp):     # hero reached showdown
                sd_reached += 1
                wtsd += 1
                if "won" in disp:
                    wsd += 1

    def pct(a, b):
        return f"{100*a/b:4.1f}%" if b else "  n/a"

    af = (p_bets + p_raises) / p_calls if p_calls else float("inf")
    print(f"=== PRO TENDENCY PROFILE: {hero}  ({n_dealt} hands dealt, {len(files)} files) ===")
    print(f"  game: NLHE 7-max PKO bounty MTT (antes + ICM + bounties) -> EXPLOIT/META reference only (clean boundary)")
    print(f"  --- preflop ---")
    print(f"  VPIP (voluntarily entered) : {pct(vpip, n_dealt)}   ({vpip}/{n_dealt})")
    print(f"  PFR  (raised preflop)      : {pct(pfr, n_dealt)}   ({pfr}/{n_dealt})")
    print(f"  VPIP/PFR gap               : {100*(vpip-pfr)/n_dealt:4.1f} pts  (tight gap = aggressive/polarized)")
    print(f"  3bet when facing an open   : {pct(threebet, threebet_opp)}   ({threebet}/{threebet_opp})")
    print(f"  --- postflop ---")
    print(f"  saw flop                   : {saw_flop}   | went to showdown (WTSD): {pct(wtsd, saw_flop)}")
    print(f"  won at showdown (W$SD)     : {pct(wsd, sd_reached)}   ({wsd}/{sd_reached})")
    print(f"  aggression factor (b+r)/c  : {af:4.2f}   (bets {p_bets} raises {p_raises} calls {p_calls} "
          f"checks {p_checks} folds {p_folds})")
    print(f"\n  CAVEAT: PKO/ICM/antes distort ranges vs our cash bot -- use as an opponent-ARCHETYPE for the exploit")
    print(f"  engine (e.g. calibrate an 'aggressive reg' node), NOT as cash ranges or a GTO/training source.")
    return {"hero": hero, "n": n_dealt, "vpip": vpip, "pfr": pfr, "3bet": threebet, "3bet_opp": threebet_opp,
            "wtsd": wtsd, "saw_flop": saw_flop, "wsd": wsd, "sd": sd_reached, "af": af}


def main():
    hero = sys.argv[1] if len(sys.argv) > 1 else "DaniC1994"
    d = sys.argv[2] if len(sys.argv) > 2 else DEF_DIR
    files = sorted(glob.glob(os.path.join(d, "*.txt")))
    if not files:
        print(f"no .txt files under {d}")
        return
    profile(hero, files)


if __name__ == "__main__":
    main()
