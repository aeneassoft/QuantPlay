"""GLYPHEN-SAMMLER für PokerSnowie (User, 2026-08-04): das Deck einmalig lernen, danach gratis erkennen.

Das ist KEIN Spiel und KEINE Messung — der Sammler versteht den Tisch bewusst nicht. Er klickt immer nur
den MITTLEREN Button (Check-oder-Call, also stets legal), damit Hände weiterlaufen und viele verschiedene
Karten erscheinen; nebenbei legt er jeden Glyph ab, den die lokale Erkennung noch nicht kennt.
Call-down bis zum Showdown ist Absicht: so sieht man volle 5-Karten-Boards statt nur Preflop-Folds.
Es ist eine Spielgeld-Trainingssession mit Auto-Rebuy — die Chips sind bedeutungslos.

DEDUP: neue Glyphen werden gegen die bereits gesammelten gematcht (gleiche Metrik wie die Erkennung),
damit nicht Dutzende fast identischer Kopien desselben Zeichens anfallen.

  python -m research.snowie_collect --iter 400
"""
from __future__ import annotations

import argparse
import os
import time

import numpy as np
from PIL import Image

from pokerbot.vision import snowie_local as SL
from pokerbot.vision import snowie_state as SS
from pokerbot.vision.snowie_bridge import _click_frac, _type_number, window_box

AMOUNT_BOX = (1766, 1234, 1878, 1282)      # das Betrags-Eingabefeld (live vermessen)

DEDUP_MIN = 0.82           # aehnlicher als das -> zaehlt als schon gesammelt


def _collect(sub: Image.Image, kind: str, seen: dict, bright: bool) -> bool:
    """Unbekannten Glyph ablegen, wenn er weder Template noch schon gesammelt ist. True = neu."""
    binz = SS._binary_bright(sub) if bright else SL._binary(sub)
    if binz.std() < 1e-6:
        return False
    for known in seen.setdefault(kind, []):
        if SL._score(binz, known) >= DEDUP_MIN:
            return False
    seen[kind].append(binz)
    d = os.path.join(SL.DUMP_DIR, kind)
    os.makedirs(d, exist_ok=True)
    sub.save(os.path.join(d, f"{kind}_{len(seen[kind]):03d}.png"))
    return True


def run(iters: int, pause: float) -> None:
    bbox = window_box()
    seen: dict[str, list] = {}
    # bereits vorhandene Templates gelten als gesehen (nicht erneut sammeln)
    for kind, bright in (("rank_b", False), ("rank_h", False), ("digit", True)):
        d = os.path.join(SL.TPL_DIR, kind)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.endswith(".png"):
                    img = Image.open(os.path.join(d, f))
                    seen.setdefault(kind, []).append(SS._binary_bright(img) if bright else SL._binary(img))
    new = {"rank_b": 0, "rank_h": 0, "digit": 0}
    times: list[float] = []
    for i in range(iters):
        img = SL.grab()
        # --- Kartenraenge (dunkle Tinte auf weissem Papier) ---
        for key in [f"board{k}" for k in range(5)] + ["hero0", "hero1"]:
            card = SL.crop_frac(img, SL.REGIONS[key])
            g = np.asarray(card.convert("L"))
            if (g > 200).mean() < 0.25:                 # leerer Slot / verdeckte Karte
                continue
            lay = SL.GLYPH_HERO if key.startswith("hero") else SL.GLYPH_BOARD
            x0, y0, x1, y1 = lay["rank"]
            sub = card.crop((int(x0 * card.width), int(y0 * card.height),
                             int(x1 * card.width), int(y1 * card.height)))
            kind = "rank_h" if key.startswith("hero") else "rank_b"
            if SL.match(sub, kind)[0] is None and _collect(sub, kind, seen, False):
                new[kind] += 1
        # --- Ziffern (helle Schrift auf dunklem Grund) ---
        for box in SS.number_fields().values():
            crop = SS._sub(img, box)
            g = np.asarray(crop.convert("L"))
            for a, b in SS._digit_boxes(g):
                ch = crop.crop((a, 0, b, crop.height))
                if SS.match_digit(ch)[0] is None and _collect(ch, "digit", seen, True):
                    new["digit"] += 1
        if SS.hero_turn(img):
            # BETRAGS-TRAINING: alle 7 Runden einen Wert eintippen, Zeit messen und das Feld ablegen —
            # danach per Auge pruefbar, ob exakt der gewuenschte Betrag steht (Genauigkeit + Tempo).
            if True:      # bei JEDER Gelegenheit messen (Rundenraster traf zu selten mit Heros Zug zusammen)
                val = round(2.0 + (i % 5) * 3.5, 2)
                t0 = time.perf_counter()
                _click_frac(bbox, "amount")
                _type_number(val)
                dt = (time.perf_counter() - t0) * 1000
                times.append(dt)
                fld = SS._sub(SL.grab(), AMOUNT_BOX)
                os.makedirs(os.path.join(SL.DUMP_DIR, "bet"), exist_ok=True)
                fld.save(os.path.join(SL.DUMP_DIR, "bet", f"soll_{val:g}_{len(times):02d}.png"))
            _click_frac(bbox, "btn_mid")                 # weiter: Check-oder-Call ist immer legal
        if i % 25 == 0:
            print(f"[{i:4d}] neu: {new['rank_b']}B/{new['rank_h']}H Raenge / {new['digit']} Ziffern", flush=True)
        time.sleep(pause)
    if times:
        srt = sorted(times)
        print(f"BETRAGS-EINGABE: n={len(times)} | Median {srt[len(srt)//2]:.0f} ms | "
              f"min {srt[0]:.0f} | max {srt[-1]:.0f} ms")
    print(f"FERTIG nach {iters} Runden — neu: {new['rank_b']} Board-Raenge, {new['rank_h']} Hero-Raenge, {new['digit']} Ziffern")
    print(f"Zum Labeln: {os.path.join(SL.DUMP_DIR, 'rank')} und .../digit")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=400)
    ap.add_argument("--pause", type=float, default=0.45)
    a = ap.parse_args()
    run(a.iter, a.pause)


if __name__ == "__main__":
    main()
