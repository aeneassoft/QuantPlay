# extraction/ — mining, heavy compute, neural training, consults

Off-line pipelines that PRODUCE the artifacts in `knowledge_base/` and train/consult. Run from the project root
as `python -m extraction.<name>`. See the root [README](../README.md) and [docs/STATE.md](../docs/STATE.md).

- **Book mining:** `extract_book.py`, `mathematics_of_poker.py` → `knowledge_base/concepts|ranges|math`.
- **Solver caches (the floor's training data):** `mass_solve.py` (RAM-adaptive parallel TexasSolver),
  `analyze_cache.py`, `build_*_data.py` + `train_*_advisor.py` (flop/turn/river/defense advisors).
- **Neural net training:** the trainers live in `pokerbot/strategy/deep_cfr*.py`; data/eval helpers here.
- **LLM / OpenAI consults (Claude + GPT-5.5/o3, vetted in-session):** `*_consult.py` → `docs/*.md` +
  `knowledge_base/theory/`. Newest: `cfr_papers_consult.py`, `math_theory_consult.py`, `hard_spots_consult.py`.
- **Heavy compute / pod:** `runpod_run.py` (provision/`--kill` a GPU pod), `deep_cfr_nlhe.py` (OpenSpiel Deep CFR
  on the pod), `qwen_sft.py` (Qwen LoRA on PokerBench).
- **Active learning:** `grounded_blindspots.py` (solver-disagreement signal) + `blindspot_radar.py` (Claude triage).

> All API output is VETTED in-session for hallucination; nets/caches are regenerable (gitignored).
