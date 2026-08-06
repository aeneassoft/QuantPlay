# Die Leiter — Princedarkness' Cash-Struktur (Stand: Roll 291€)

> Kurzkauf-Barbell mit Ratsche. Kelly-gerechnet auf die gemessene Varianz (SD 22,4bb/Hand),
> Fat-Tail-korrigiert (Halb-Kelly), Zustandsgesetze eingebaut. Regeln bewusst SIMPEL —
> jede Regel passt auf eine Karte.

## 1. DIE LEITER — die Roll bestimmt die Stufe (bei Session-Start ablesen)

| Roll | Basis-Stufe | Einkauf | Ernte-Stufe (max 1×/Tag) | Einkauf |
|---|---|---|---|---|
| unter 250€ | NL50 | **20€ (40bb)** | — | — |
| 250–600€ | NL50 | **20€ (40bb)** | NL100 | **40€ (40bb)** |
| 600–1.200€ | NL100 | **40€ (40bb)** | NL200 | 80€ (40bb) |
| 1.200–2.000€ | NL100 | 40€ (40bb) | NL200 | 80€ (40bb) |
| ab 2.000€ | NL100 | voll (100bb) erlaubt | NL200 | 80€ (40bb) |

**Immer 40bb. Nie mehr. Kein Nachladen über 40bb.**
**Verbotszone: NL2, NL5, NL10 — niemals, egal was. (Messbar tote Zonen.)**

## 2. DIE RATSCHE — wann raus aus dem Tisch

- **Doppelt = Kasse.** Stack ≥ 80bb → aufstehen, Gewinn in die Roll, neu 20/40€ einkaufen
  (gleicher oder anderer Tisch). Die Verlust-Kappe ist nur intakt, solange der Stack kurz ist.
- **Stack weg = 10 Hände Premium.** Nach jedem verlorenen Buy-in: die nächsten 10 Hände nur
  Premium-Range, mechanisch. (Das gemessene τ-Protokoll.)

## 3. DER TAG — wann Schluss und wann der Schuss

- **Session = 45 Minuten. Wecker stellen. Wecker klingelt = letzte Hand.** (Die Sitzungs-
  Klippe kommt im letzten Drittel — das letzte Drittel wird einfach nie gespielt.)
- **−2 Buy-ins am Tag = Tag beendet.** Keine Ausnahme, kein "eine noch".
- **DER SCHUSS: +2 Buy-ins am Tag im Plus → EINE Ernte-Session auf der nächsthöheren
  Stufe erlaubt** (40bb, aus dem Tagesgewinn bezahlt). Verliert der Schuss seinen Buy-in →
  zurück zur Basis, kein zweiter Schuss am selben Tag.
- **Ein Tisch. Immer nur einer.**

## 4. DIE KONTROLLE — jeden Tag 30 Sekunden

`python -m research.pd_day --dir <Tagesordner>` — drei Zahlen prüfen:
VPIP ≤ 45 · Limp = 0 · kein Verlust > 1 Buy-in. Zwei Tage mit Langeweile-Signatur auf der
Basis-Stufe (VPIP > 50) → die Stufe liegt unter seiner Bedeutungsschwelle → Basis eine Stufe HOCH
(nicht runter — sein Gradient ist invertiert).

---
*Warum diese Zahlen: 40bb-Kurzkauf kappt den Monsterpot strukturell (sein einziges großes Leck),
braucht bei NL50 nur ~8–16 bb/100 und bei NL100 ~16–31 bb/100 zur Kelly-Rechtfertigung (voll/halb),
hält ~86% der Roll permanent vom Tisch (Barbell) und spielt in seinem Ereignis-Band (hohe
Entscheidungsdichte). Die Ratsche konserviert die positive Schiefe. Skin bleibt im Spiel —
nur der Ruin nicht.*
