# PRÄZISIONS-DOKTRIN — optimiere Entscheidungen, verändere sie nicht (User, 2026-07-06)

> Entstanden aus dem empirischen Befund der Nacht 07-05/06: JEDER Verhaltens-Hebel trug
> Interaktionsrisiko (Familie E: Sieger fraßen sich gegenseitig; Live-Bruch: Hebel x Resolver
> −58 statt −20). KEIN Präzisions-Schritt schlug je zurück (Memoisierung byte-identisch, exakte
> River-Enumeration, Determinismus, Census-Bäume). Konsequenz: die Verbesserungs-Klasse wechselt.

## Das Gesetz
Zulässig ist eine Änderung, wenn sie DIESELBE entscheidungstheoretische Größe GENAUER berechnet
(Konvergenz zum selben Fixpunkt; Kosten = nur Rechenleistung). Unzulässig als Default ist jede
Änderung des Ziels pro Klasse (Thresholds/Discounts/Menü-Erweiterungen/Modalitäts-Knöpfe) —
solche Hebel nur noch als Ausnahme mit klassen-dichter Paar-Evidenz UND Live-Bestätigung, nie
gestapelt.

## Zulässige Schritte (die Präzisions-Queue)
1. Resolver-Konvergenz: iters/accuracy pro Solve hoch (kein Latenz-Limit vs GTOW); erreichte
   Exploitability pro Solve wird geloggt (Q3-Fix aktiv) — der Konvergenz-Auditor ist das Gate.
2. Exakte Turn-Enumeration statt MC an Entscheidungsgrenzen (eliminiert ~0.9pp MC-SE).
3. Range-Wahrheit statt Range-Hebel: Tracker-Änderungen (inkl. v3.3-Narrowing) validieren sich
   ausschließlich als Range-Fehler-Reduktion vs GTOWs AUFGEDECKTE Karten (13.5k Hände,
   check_range_l1-Prinzip). Nur wahrere Ranges dürfen den Resolver füttern.
4. Flop-Library (Precompute; docs/FLOP_LIBRARY.md-Auflagen gelten).
5. PFLASTER-NETZE (User-Direktive): KEIN primäres Netz. Kleine CFV-Netze als Komponenten, die
   einen SOLVE tiefer/genauer machen — erstes Pflaster: Turn-Boundary-CFV-Netz schaltet den
   Flop-Resolver frei (Depth-Limit am Turn, Netz bewertet das Blatt). Gate 0 (Leduc, exakte
   Exploitability) validiert die Maschinerie; danach Gate 1 = River/Turn-Netz klein
   (VALUE_NET_SPECS.md-Synthese, Pilot-Leiter, Suit-Aliasing = Blocking-Gate).

## Der Anker (einzige validierte Benchmark)
Tag v2 = −19.70 ± 4.37 live (n=2,393), Platz 11. JEDER Schritt misst dagegen: gepaarte Exporte
stets mit v2.2-Flags-Arm; Live-Läufe stets gegen −19.70 gelesen. Die Analyzer-Hebel der Nacht
(v3.3/OBM/PURIFY/TDA) bleiben archivierte Fakten, berühren den Live-Bot aber erst wieder, wenn
sie die Präzisions-Prüfung (Range-Wahrheit / Konvergenz / Live-Paar) bestehen.
