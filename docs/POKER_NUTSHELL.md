# POKER IN A NUTSHELL — die fundamentale Linie (User-Zeichnung, 2026-07-06)

> Die Essenz, aus der die ganze Bot-Architektur folgt. Keine Metapher — ein Diagnose-Werkzeug, das
> mehrere GEMESSENE Befunde vorhersagt. Bild: die Handskizze des Users.

## Das Bild
Y-Achse = HANDSTÄRKE. Die naive Linie: bette proportional zur Hand ("ehrliches" Poker). Der Edge liegt
in der WELLE drumherum — der bewussten Abweichung: OVERBET (über der Linie) / UNDERBET (unter der Linie).

Zwei ANKER (berechenbar, die Kreise):
- **Preflop** = "pure statistics + opponent matching" — reine Berechnung (Blueprint).
- **River = „The Bill"** — wo die Rechnung beglichen wird; terminal, simple bet/check/bluff-Mechanik.
  Bankroll-Wahrheit: mehr Bluffen → höhere Varianz → Bankroll-Schwankung.

Dazwischen die WELLE = Flop/Turn = Spieltheorie (Abweichung von der Handstärke).

Zwei ZWECKE der Abweichung (das V):
- **Fold Equity** — mehr betten als die Hand rechtfertigt → Folds erzeugen.
- **Induced Confidence / Extraction / Milking** — weniger betten / trappen → Gegner selbstsicher halten, melken.

Der TIEFSTE Punkt: **Seesaw (Game Theory) → always switching up over time → unpredictable + noise.**
Nie in einem Modus verharren; ewig oszillieren, sonst wird man lesbar.

## Warum das die fundamentale Linie IST — es erklärt unsere Messungen
1. **Seesaw ⇒ der v8-Live-Bruch.** PURIFY flachte das Mixing ab (modal) → SLOWPLAY feuerte nie → Check-Range
   transparent → −20 auf −58 live. "Hör auf zu schaukeln = werde vorhersehbar" — exakt gemessen.
2. **Das V ⇒ die Value/Bluff-Trennung + Polarisierung** (B/(P+B) = das Gewicht je Ast am River).
3. **Die Anker ⇒ die Straßen-Doktrin** (Preflop/River rechnen, Flop/Turn = Welle, Fold-Equity-Job).
4. **„The Bill" ⇒ River-Primacy** (dort begleicht sich die ganze Hand).

## Konsequenz für die Bot-Linie (bindend)
- Der Bot ist ein SEESAW, kein Fixpunkt.
- Preflop/River: rechnen (Anker halten).
- Flop/Turn: die Welle ERZEUGEN — Over/Underbet für Fold-Equity ODER Extraction, balanciert UND zeitlich
  unvorhersehbar (LINE_U-Seed, Mixing, Deception — NIE abflachen; das ist die Purify-Live-Lektion als Gesetz).
- Balance ist nicht-verhandelbar (Seesaw), aber das Schaukeln SELBST ist der Edge; gegen adaptive Gegner
  wird das Umschalten über Zeit (Red Queen) zum Exploit.
- Bankroll/Varianz = bewusste Achse (mehr Bluffen = mehr Varianz). Noch NICHT als expliziter Regler
  formalisiert — Kandidat: ein Varianz/Bankroll-Dial über der Bluff-Frequenz.
