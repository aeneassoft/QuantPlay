# HU-OPTIMAL-KARTE — Voll-Assessment vor v9 (2026-09-01)

**Methode:** Vier Quellensorten, getrennt erhoben und hier synthetisiert: (1) Messdaten der
GPU-Staffel (Tiefen-Replay 571 Entscheidungen mit Aktions-EVs, HH-Mine, GPU-Audit, Gate-Historie),
(2) dokumentierte Baustellen (Niveau-Audit/Armee/Root-Sweep, dedupliziert gegen das seit 30.08.
Gelandete), (3) Code-Ist-Verifikation (Flag-Defaults, Bäume, Textur-Systeme — jede Zeile file:line-
geprüft, Agent „code-ist"), (4) 6max-Sharing-Struktur (Agent „sixmax-transfer").
**6max-Spalte:** AUTO = wirkt automatisch (geteiltes Substrat: cards/evaluator/equity/postflop) ·
BRÜCKE = wirkt automatisch in HU-kollabierten 6max-Pötten (Prince-Takeover in six_server-GTO-Modus,
`--hybrid`-Export, Snowie-Brücke — praktisch ein Großteil der River-Spots) · PORT = Technik
übertragbar, braucht Arbeit · NEIN = HU-spezifisch.

**Leitbefund (Tiefen-Replay, EV-gewichtet):** Liegengelassen : Fehler = **1,6 : 1**. Die Karte ist
darum nach EV-Hebel sortiert, nicht nach Alter der Baustelle.

---

## A. ENTSCHEIDUNGSQUALITÄT (das Geld)

**A1 · Das fehlende River-RAISE-Spiel — größte Einzellücke (31,1bb OVERFOLD in 970 Händen).**
Evidenz: Tiefen-Replay — fold→raisejam mit Jd8h/9c5c (Bluff-Raises!), fold→call; dazu VERPASST_VALUE
5,7bb (call→raisejam) und VERPASST_BLUFF 5,5bb. Der TexasSolver-Census-Baum HAT River-Raise-Arme
(35/65/100/150 + raise 50/100, resolver.py:21-26), der GPU-Baum auch — aber die Fold-Entscheidungen
FRAGEN den Solver nie (Play/Chirurgie-Trigger war ≥30bb; die Ernte sitzt in 8–30bb-Pötten).
Fix: Play-Guard mit tiefem Trigger (~15bb) + fp16 fürs Latenz-Budget. **→ v9-Kern.** [6max: BRÜCKE]

**A2 · SIZE-Präzision (9,0bb).** raise2.7→raisejam, bet1.5→bet0.35 — die Solver-Size ist bekannt,
wird aber nicht gespielt; der r8-Chirurgie-Override hardcodet zudem 0,75·Pot (improver.py, Kollision
mit RIVER_ECALL-Sizing — Totcode-Karte „Doppel-Resolver-Kreuzung"). Fix: Baum-Arm-Size ausgeben
(im Play-Guard bereits korrekt implementiert). **→ v9-Kern.** [6max: BRÜCKE]

**A3 · Fehl-Value-Bets (VERLUST_AGGRO 11,5bb v4 / 27,4bb Kontrolle).** Teiladressiert durch
wert_bremse (3× repliziert +8); Rest = Play-Guard-Bereich zwischen den Schwellen. [6max: BRÜCKE]

**A4 · VERLUST_CALL ist im EV-Maß die KLEINSTE Kategorie (4,1bb).** Die berühmte −121bb-AIVAT-Zelle
war überwiegend Karten-Realisierung (#3003011: −137bb real, +0,6bb EV-Diff). Lehre bindend: **AIVAT-
Zellen sind Realisierungs-, nicht Entscheidungs-Attribution — Priorisierung künftig nur über
Aktions-EVs** (tiefen_replay-Maschine). Keine weitere Defense-Runde rechtfertigbar. [6max: AUTO als Lehre]

**A5 · Turn/Flop-Stufe ungelöst.** Turn: TurnCFR gebaut+kreuzvalidiert (OOP r=0,944), Einsatz zu
teuer/leise (r9_turn 3/3904); Flop: keine GPU-Stufe; beide Straßen spielen Advisor/Heuristik
(Solver-EV-Fehler dort noch unvermessen — die River-6,9bb/100 sind NUR der River). Fix-Pfad:
kanonische Board-Bibliothek (A6) statt live-Solves. [6max: BRÜCKE/PORT]

**A6 · Kanonische Solve-Bibliothek statt Board-Kategorien.** Suit-ISO ist die einzige verlustfreie
Board-Abstraktion (1.755 kanonische Flops — mit der Batch-Maschine bei 0,3s/Spot vollständig
enumerierbar; Turn ~16k). ISO-Cache existiert, default OFF (gto_oracle.py:54, roher env-Read).
Fix: ISO ON (Messung), dann Flop/Turn-Bibliothek für Standard-Geometrien+Range-Prototypen.
[6max: BRÜCKE — dieselben Boards]

**A7 · Preflop-Stack-off (GTOW-Klasse D, −13,8bb/Hand-Zelle).** stackoff_bremse gebaut, 10/10
Selbsttests, Selfplay-stumm (1 Trigger/400) — als GTOW-Arm mitzuführen, Beweis nur am Anker.
[6max: PORT — Klassen-Logik gleich, Ranges anders]

## B. RANGE-MODELL (der Input des Solvers)

**B1 · Tracker-Rekonstruktion trägt die River-CALL-Defense nicht** (Trennschärfe 0,65/0,53; Ranges
nach 3 Barrels 700–900 Combos). ABER: EV-relevant kippt der Range-Tausch nur 5% der River-URTEILE
(Tiefen-Replay) — die Big-Pot-Urteile sind range-robuster als gedacht; die Range wirkt v.a. auf die
MISCHUNGEN (34% Roh-Kipp). Konsequenz: Range-Struktur-Arbeit (Linien-Konsistenz, Bet-Range-DB aus
Census+Showdowns, strukturelle Bluff-Mengen) ist **Frequenz-/Politik-Hebel, nicht Urteil-Hebel** —
wichtig, aber hinter A1/A2 einzureihen. [6max: BRÜCKE via make_seeded_tracker + PORT für Priors]

**B2 · hand-not-in-range** (Flop-Resolver 0/3-Erstflug): im GPU-Pfad per Hero-Injektion gelöst;
im TexasSolver-Pfad offen (bot.py:1104-Ansatz dokumentiert). [6max: BRÜCKE]

**B3 · Preflop-Prior-Grobheit** (Limp-Raise-Inversion, symmetrischer 3bet-Prior — Armee rest[21]).
[6max: PORT]

## C. RECHENWERK / GPU

**C1 · Doppel-Resolver am River** (GTOW-Kanal: TexasSolver-ON + GPU-Guard, 13,5s Kaltstart).
A/B „GPU ersetzt TexasSolver-River" (POKERB_RESOLVER=0) = Protokoll-Arm B2, fertig vorregistriert.
**C2 · fp16** (+64% gemessen, half=True, default OFF — v9 nutzt es, A/A muss es beweisen).
**C3 · Entropie-Anker (Leal):** CFR+ wählt beweisbar niedrig-Entropie-Polytop-Member; MMD-artiger
Anker → Max-Entropie = besserer Hedge (Kuhn 25/25, extensive-form ×5,6). Gate: Adversar-Achse
(exploit_jagd/Fable), NIE der Spiegel. [alle 6max: BRÜCKE]

## D. CODE-GESUNDHEIT (verifiziert, file:line beim Agenten-Report)

**D1 · AKTIV_FALSCH — die HU-Web-App spielt eine nie gemessene Konfig:** kein PRINCE-Profil,
exploit=True, volle r8_stack-Kette + RAISE_NARROW=1.0 (server.py:19-43 + Launcher). Die Exploit-
Deviationen und der GTO-Guard arbeiten GEGENEINANDER am selben River-Knoten. **Sofort-Fix (Kanal-
Hygiene, kein Gate nötig: die App soll die GEMESSENE v5-Definition spielen):** PRINCE + exploit-OFF
in server.py. [6max: six_server hat die Env-Flags korrekt — prüfen, ob PRINCE dort auch fehlt]

**D2 · AKTIV_FALSCH — die 9 AUDIT_FIX-Bugs laufen live** (Default 0, nicht in PRINCE_PROFILE;
bot.py:62) **und die Advisor-Rollen-Inversion in 3bet-Pots ebenso** (ADVISOR_ROLE_POS=0, bot.py:65-70).
Fix-Weg: als GTOW-Arm-Flags (der Gym-Kanal ist flag-frei by design); Erwartung vorregistrieren.
[6max: BRÜCKE]

**D3 · Stille Advisor-Loads** (advisor.py:62-70, jede Exception → still Heuristik, 0 Log-Pfade) +
kein Golden-Vector, keine .pt-SHA (Niveau-Audit Rang 7, „Fundament aller bb-Zahlen"). ~2h. [AUTO]

**D4 · Sechs Board-Textur-Sichten** (1 kanonische + 3 Duplikate des 5-Klassen-Kollapses in
advisor/bot/gto_benchmark + 2 abgeleitete) → EINE Quelle (postflop.classify_board), Rest Konsumenten;
Byte-Identitäts-Gate als Refactor-Schranke. [AUTO — postflop ist der breiteste geteilte Kanal]

**D5 · RAISE_NARROW-Importzeit-Falle:** global auf ALLE Tracker-Konsumenten; ein späteres
use_resolver=True im selben Prozess macht v8-K3 scharf ohne Flag-Änderung. Fix: harter Code-Guard
(Kontraindikation erzwingen statt Kommentar). **D6 ·** gtowizard-Adapter ruft setze_env() nicht
(Stack ohne Env-Hälfte möglich); button_disziplin hartkodiert Blinds 50/100. **D7 ·** OppModel
wird unter PRINCE gefüttert aber nie konsumiert (state-tragender Totcode). **D8 · TOT_HARMLOS**
(kein Handlungsbedarf, dokumentiert): brain/ komplett, models/-Altbestand, adaptive/unified_exploit/
playbook/corset/distill/deep_cfr*-Waisen.

## E. MESS-/BEWEISKANAL (die v8-Lektion institutionalisieren)

**E1 · Der Spiegel bepreist Ernte-Präzision nicht** (v8-Postmortem; Kanal-Sättigung, nz_median
1,9bb). Vor jedem Präzisions-Build: $0-EV-Beweis auf den GTOW-Händen (Aktions-EV-Maschine) als
Vorgate; mittelfristig **Re-Solver-Proxy-Gegner** im Gym (GPU-Solver als Gegner-Politik) — der
einzige $0-Kanal, der A1/A2/C3 bepreisen kann. **E2 · GTOW-Anker v5** = der Absolut-Beweis; alles
seit v4 ist Selektions-Kanal (wartet auf User-Kommando; Protokoll + Arm B1/B2 fertig). **E3 ·**
AIVAT-light im Mirror (Rang 1, offen), FDR-Ledger/Pocock (Rang 3/4, teils), Deck-Bank-Register
(Rang 10, Disziplin statt Code), LBR v2 als Taufe-Pflicht (Rang 13, offen). **E4 ·** 6max-Messkanal:
der 85,9%-Grade misst den LIGA-tag-Kern, nicht bot.py — nur `--hybrid` misst das Produkt; pargate6
existiert nicht (SixMaxBot.rng ungeseedet = Paarungs-Blocker, Armee rest[32]).

## F. 6MAX-TRANSFER-SUMME

Automatisch (AUTO): alles in engine/ (cards/evaluator/equity), postflop.py (breitester Kanal — von
bot.py UND der Liga direkt genutzt), D3/D4-Hygiene. Über die GEBAUTE Brücke (BRÜCKE): der komplette
HU-Stack inkl. aller v9-River-Verbesserungen wirkt in HU-kollabierten 6max-Pötten (six_server-GTO-
Modus, --hybrid, Snowie) — das ist praktisch der Großteil der 6max-River-Entscheidungen. Bewusst
NICHT übertragen: die AUSLESE-Guard-KETTE in der Brücke (nur Env-Flags wirken — Verdrahtungs-
Entscheid, den v9 prüfen sollte). HU-spezifisch bleiben: range_tracker-Walk (2-Sitze hart),
button_disziplin, Blueprint. Multiway-echt (3+ am River) braucht eigene Arbeit: Multiway-Equity
fehlt beidseits, F(s)-Fold-Kurve ist Ein-Gegner, Advisor-Priors HU-trainiert.

---

## DER v9-SCHNITT (User-Auftrag: bauen → vs eingefroren → vs Champion)

**v9 = das River-Ernte-Paket:** Play-Guard tief (Trigger ~15bb, fp16, Solver-Sizes aus dem Baum,
adressiert A1+A2+A3-Rest) + wert_bremse darunter + stackoff_bremse (GTOW-stumm-Härtung) auf der
r6_button-Kette. Vorgates: $0-EV-Ernte-Beweis auf Nacht-2 (E1) → Latenz-Smoke → A/A (fp16-
Determinismus!) → Treppe vs r8_stack (Champion v5) und vs basis (eingefroren). Vorregistrierung:
Spiegel-Erwartung NEUTRAL bis leicht positiv (v8-Lektion — der Spiegel sieht Ernte kaum); das
Ship-Kriterium ist Nichtverschlechterung im Spiegel + klar positiver EV-Ernte-Beweis auf der
GTOW-Achse. Parallel (kein Gate nötig): D1-Kanal-Hygiene der HU-App.
NICHT in v9 (bewusst): Range-Struktur-Runde (B1 — Politik-Hebel, braucht E1-Proxy-Kanal),
Entropie-Anker (C3 — braucht Adversar-Gate), Flop-Bibliothek (A6 — eigene Runde), D2-Flags
(GTOW-Arm, nicht Gym).
