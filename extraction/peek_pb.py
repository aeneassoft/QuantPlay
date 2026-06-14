"""Load full PokerBench train (cached after first run), count preflop, show 3 real preflop rows."""
from datasets import load_dataset

ds = load_dataset("RZ412/PokerBench", "default", split="train")
print("train size:", len(ds), flush=True)
pre = [r for r in ds if "flop comes" not in r["instruction"].lower()]
print("preflop rows:", len(pre), flush=True)
for r in pre[:3]:
    print("=" * 90, f"\nOUTPUT={r['output']!r}\n{r['instruction']}\n", flush=True)
