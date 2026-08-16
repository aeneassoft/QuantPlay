# GPU_PLAN.md — die 3080 Ti im Autogym (gemessen entschieden, 2026-08-16)

**Messungen dieses Abends:** CUDA laeuft (3080 Ti, 12,9 GB). Der gebatchte Advisor-Pass
(1300x20) ist auf GPU NICHT schneller als CPU (3,20 vs 3,52 ms — Launch+Transfer fressen den
Gewinn bei kleinen Batches). Profil davor: die Live-Schleife war Batch-1-Overhead, per
CPU-Batching geloest (2,2x). **Folgerung: Live-Inferenz bleibt CPU; die GPU bekommt die
Massen-Jobs.** Das ist keine Vermutung, sondern der Mikro-Benchmark.

## Job 1 — DIE EXAKTE 169x169-EQUITY-MATRIX (der Poker-spezifische GPU-Kernel)
Browns Referenz-Bauplan (brown_vnm_169.md): je Paarung alle C(48,5)=1.712.304 Boards exakt
enumerieren. Gesamtvolumen ~5x10^10 Hand-Evaluationen: **CPU ~2 Tage (24 Kerne), GPU mit
tensorisiertem 7-Karten-Evaluator ~Minuten.** Genau das ist 'die Grafikkarte fuers Pokerspiel
tunen': ein Batch-Evaluator als Integer-Tensor-Kernel (Rank-Histogramme + Flush-Masken als
torch-Ops), Poker-spezifisch, wiederverwendbar fuer jede kuenftige Enumeration.
ERTRAG: die Fraction-taugliche E1-Referenz fuer Check V1 value_ordnung (Sieg/Split als exakte
INTEGER-Zaehler -> echte Brueche), Ersatz fuer das nicht referenz-taugliche preflop_eqmatrix.json
(MC 600), und die Brown-Taxonomie (88/27/54) lokal reproduzierbar.
VALIDIERUNG (vorregistriert): 200 zufaellige (Paarung, Board)-Stichproben muessen treys
BIT-EXAKT treffen; Zeilensummen-Symmetrie W(i,j)+W(j,i)=1; AA-vs-random als bekannter Anker.

## Job 2 — Offline-Rueckschau-Grading (Orakel-Beschleuniger)
decisions.jsonl.gz im Batch nachgraden (Equity-MC fuer L-Checks): ein Prozess, grosse Batches,
keine Worker-Contention — der Einwand gegen Live-GPU gilt hier nicht.

## Job 3 — v4-Value-Net-Training (der geborene Einsatz)
Gate-0/CFV-Netze (DeepStack-Spez. 7x500) und jedes Deep-CFR-Training: 12,9 GB reichen weit.
Die 3080 Ti ist das TRAININGS-Geraet des v4-Pfads; der Pod bleibt CPU-Self-Play.

## Nicht tun (gemessen/entschieden)
- Advisor-Live-Inferenz auf GPU (Benchmark oben). 22 Worker x 1 GPU = Contention.
- GPU-'Tuning' im Sinne von Takt/Treiber-Spielerei: nichts davon schlaegt den richtigen Kernel.

**Reihenfolge:** Job 1 als naechster Build (eigene Session, der Evaluator ist ein Tages-Bauwerk
mit Validierungs-Gate), Job 2 danach als Nebenprodukt desselben Evaluators, Job 3 mit dem
v4-Einstieg.
