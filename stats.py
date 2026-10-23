"""stats.py - paired comparison with bootstrap 95% CI and a paired sign-flip permutation test. Offline.
Usage: python stats.py [results.jsonl] [scored.jsonl] [baseline_strategy]
Compares every other strategy with the baseline on the same (scenario, topic, run) trials."""
import json, sys, random
from pathlib import Path
B = Path(__file__).resolve().parent
a = (sys.argv + [None] * 3)[1:4]
RF, SF, BASE = a[0] or "results_v3.jsonl", a[1] or "scored_v3.jsonl", a[2] or "linear"
L = lambda p: [json.loads(l) for l in open(B / p, encoding="utf-8") if l.strip()] if (B / p).exists() else []
R, S = L(RF), L(SF)
key = lambda r: (r["scenario"], json.dumps(r["topics"]), r["run"])
METRICS = {  # name: (rows, extractor)
    "success (ok)": (R, lambda r: float(bool(r["ok"]))),
    "clean": (R, lambda r: float(bool(r["ok"] and not r.get("junk_leaked") and not r.get("junk_in_text")))),
    "total_tokens": (R, lambda r: r["total_tokens"]),
    "latency_excl_backoff_s": (R, lambda r: min(r["latency_excluding_backoff_s"], 120)),   # capped: one outlier was ~37,000s
    "faithfulness": (S, lambda r: r["judge"]["faithfulness"] if isinstance(r.get("judge"), dict) else None),
    "coverage": (S, lambda r: r["judge"]["coverage"] if isinstance(r.get("judge"), dict) else None)}

def paired(rows, f, a, b):
    ra = {key(r): f(r) for r in rows if r["strategy"] == a and r["scenario"] != "apifail"}
    rb = {key(r): f(r) for r in rows if r["strategy"] == b and r["scenario"] != "apifail"}
    return [rb[k] - ra[k] for k in ra if k in rb and ra[k] is not None and rb[k] is not None]

def test(d, n=5000, seed=0):
    rnd = random.Random(seed); m = sum(d) / len(d)
    boots = sorted(sum(rnd.choice(d) for _ in d) / len(d) for _ in range(n))
    ext = sum(abs(sum(x * rnd.choice((-1, 1)) for x in d) / len(d)) >= abs(m) - 1e-12 for _ in range(n))
    return m, boots[int(.025 * n)], boots[int(.975 * n)], (ext + 1) / (n + 1)

strats = sorted({r["strategy"] for r in R} - {BASE})
print(f"Paired differences vs baseline '{BASE}' (strategy - baseline), apifail excluded\n")
print(f"{'strategy':14}{'metric':26}{'pairs':>6}{'mean diff':>11}{'95% CI':>22}{'p (perm)':>10}")
for s in strats:
    for name, (rows, f) in METRICS.items():
        d = paired(rows, f, BASE, s)
        if len(d) < 5: continue
        m, lo, hi, p = test(d)
        print(f"{s:14}{name:26}{len(d):>6}{m:>11.3f}{f'[{lo:.3f}, {hi:.3f}]':>22}{p:>10.4f}")
print("\nA CI that excludes 0 (and small p) means the difference is unlikely to be run-to-run noise.")
print("Many comparisons are made, so treat p-values near 0.05 as weak evidence.")