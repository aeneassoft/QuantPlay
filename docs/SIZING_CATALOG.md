# SIZING-KATALOG — Princedarkness vs. Bot vs. GTOW-Census (2026-07-06)

> User-Direktive: eigene Bet-Sizings/Strategien entwickeln und KATALOGISIEREN, inspiriert vom eigenen
> Spiel ("Princedarkness", CoinPoker). Quelle: 1.078 Hände Feb–Jul 2026 (Downloads/CoinPoker_Princedarkness
> _2026-02-01_to_2026-07-01_Cash.txt), gemined via `research/coinpoker_style.py` + Sizing-Walk.

## Die Princedarkness-Signatur (gemessen)
| Dimension | Wert | Bot heute (Census-Tree) |
|---|---|---|
| River-Bets >1.5×Pot | **43%** (Extreme bis 26×!) | River-Grid 0.35/0.65/1.0/1.5 (Modal 0.65) |
| Turn-Bets >1.5×Pot | 24% | Turn-Grid 0.35/0.75(/1.35) |
| Flop-Bets >1.5×Pot | 21% | Flop-Modal 0.35 |
| River-RAISES >1.5×Pot | **62%** | Raise-Snap 0.60 |
| Preflop-Open modal | 3.0× (bis 12×) | 2.25× (Census) |
| Open-Limp | 19.4% | 0 (GTOW_NOLIMP) |
| Flop-C-Bet | nur 46.9% | höher | 
| Stil-Kern | **groß oder gar nicht** — maximal polarisiert | frequenz-treuer, kleiner |

## Die zwei Wahrheiten (ehrlich, gemessen)
1. **"60% nicht analysierbar" ist überwiegend FORMAT, nicht Stil-Transzendenz:** CoinPoker-ANTE-Games
   (₮3.20/Hand) + Format-Quirks sind Analyzer-"Unsupported". Und der LIVE-Leaderboard-Gegner ist der
   Ruse-RE-SOLVER: Off-Tree-Sizes verwirren ihn nicht (gemessen: Translation-Attacke refuted, Off-Tree
   erntete 0 — docs/GTOW_DOSSIER.md, 13,5k Hände). Sizes "die GTOW nicht kennt" sind KEIN Gratis-Edge
   auf dem Leaderboard.
2. **Der verwertbare Kern: Overbets vs. GECAPPTE Ranges sind solver-LEGALE Value-Maximierung** (der
   +98bb-Jam war GTO-legal; money_mine: river|villain_folded|huge = unser Top-Drucker +165 seit v2.2).
   Die Signatur zeigt exakt auf die River-Mission-Lücke. Übersetzung in Leaderboard-Hebel = die
   C1/eCall/Mr-Orange-Schiene — SELEKTIONS-bewusst (eq-vs-Calling-Range), nie Frequenz-blind (4× refuted).

## Katalog → Hebel-Mapping (jeder = eigener Arm, volle Leiter)
| Signatur-Element | Hebel | Status |
|---|---|---|
| River-Overbets (43%) | `POKERB_OVERBET_MENU` (eCall-Menü +2.0×/2.5×, Guard e_call≥0.70 auf den neuen Armen) | **GEBAUT 2026-07-06**; Stress 20=Baseline ✓ (nach 1 Tune: sizer.*.thin-Katastrophe gefangen), Replay-Delta 0 ✓; Arm in Familie D |
| Turn-Overbets (24%) | `POKERB_TURN_OVERBET` (Resolver-Turn-1.5×-Arm) | existiert (Q7); Arm in Familie D |
| Barrel-Kohärenz ("groß oder gar nicht") | `POKERB_BARREL_DISCIPLINE=0.18` | existiert (v2.3-Ära-Gates); Arm in Familie D |
| River-Raise-Overbets (62%) | Raise-Menü-Erweiterung | TODO (nächste Runde; braucht raise-Snap-Erweiterung) |
| Riesen-Overbets 3×+ vs capped | L2 Mr-Orange (perturbiertes Eq, bewiesene Leine) | Post-Ladder-Build |
| Limps/Open-Sizes | NICHT übernehmen vs GTOW (Census-EV-geschützt; SB-Fold-Clamp-Lektion) | vs HUMANS später |

## Familie D (Seed 57, Blöcke 58000/60000/62000/64000, Tage 60–63)
anchor_d (PRINCE inkl. v3.3) · tob_d (TURN_OVERBET) · bd_d (BARREL_DISCIPLINE 0.18) · obm_d (OVERBET_MENU).
Verdikt-Regeln wie gehabt: Δ > max(1.5, 2·SE) vs anchor_d, Effekt-Ort-Check, max. ein Sieger direkt.
