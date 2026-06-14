"""One-off: query the Perplexity API (search-grounded) for (1) available poker GTO datasets/databases and
(2) recent GTO + exploitative-play scientific publications. Prints the answer + the raw CITATIONS so we can
verify every claim (Perplexity is search-grounded but still mis-attributes -> we vet against the URLs).

Key is read from the file (never hardcoded). Run: python -m extraction.perplexity_search
"""
from __future__ import annotations

import json
import urllib.request

_KEYFILE = r"C:\Users\hampe\Desktop\Secret keys\AI\Perplexity API key.txt"
KEY = open(_KEYFILE, encoding="utf-8").read().strip().splitlines()[0].strip()

_SYS = ("You are a precise research assistant for a poker-AI engineer. Cite REAL sources only. For every "
        "dataset or paper give the exact name/title, authors, year, and a working URL. If you are NOT sure "
        "something exists, say 'UNCERTAIN' explicitly rather than guessing. Never invent dataset names, "
        "paper titles, authors, or URLs.")

Q1 = ("List publicly AVAILABLE datasets / databases for No-Limit Texas Hold'em poker that a researcher can "
      "download or access: (a) GTO/solver solution dumps, (b) hand-history corpora, (c) bot self-play data, "
      "(d) benchmark decision sets. For each: name, contents, approximate size, license, and exact URL. "
      "Consider e.g. PHH / pokerkit hand-history datasets, the released Pluribus/Libratus hands, "
      "RZ412/PokerBench on HuggingFace, GTO Wizard / open-solver outputs. Only list ones that really exist; "
      "mark anything uncertain.")

Q2 = ("List scientific publications (papers / arXiv preprints), ~2019-2026, on: (a) GTO / Nash-equilibrium "
      "computation for poker and large imperfect-information games, and (b) EXPLOITATIVE / opponent-modeling "
      "and safe-exploitation play. For each: exact title, authors, year, venue, and arXiv/DOI URL. Consider "
      "ReBeL, Player of Games, Student of Games, DeepNash/R-NaD, Deep CFR, LBR (local best response), safe "
      "opponent exploitation (Ganzfried/Sandholm). Only real papers with correct titles/authors.")


def ask(prompt: str, model: str = "sonar-pro") -> tuple[str, list]:
    body = {"model": model, "messages": [{"role": "system", "content": _SYS},
                                         {"role": "user", "content": prompt}]}
    req = urllib.request.Request("https://api.perplexity.ai/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=180).read())
    msg = r["choices"][0]["message"]["content"]
    cites = r.get("citations") or r.get("search_results") or []
    return msg, cites


def _show(title: str, prompt: str):
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78, flush=True)
    try:
        msg, cites = ask(prompt)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}")
        return
    print(msg)
    print("\n--- CITATIONS (verify these) ---")
    for i, c in enumerate(cites, 1):
        print(f"[{i}] {c if isinstance(c, str) else (c.get('url') or c.get('title') or c)}")


def main():
    _show("Q1: AVAILABLE GTO DATASETS / DATABASES", Q1)
    _show("Q2: GTO + EXPLOITATIVE-PLAY PUBLICATIONS", Q2)


if __name__ == "__main__":
    main()
