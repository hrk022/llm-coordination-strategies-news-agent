"""compare_versions.py - paired v1 vs v3 comparison (same strategy, same scenario/topic/run), with bootstrap 95% CI.
Usage: python compare_versions.py scored_v1_newjudge.jsonl scored_v3.jsonl [strategy ...]
Default strategies: linear dynamic_graph. Scenarios: normal sparse flood noisy (the ones both versions ran)."""
import json, sys, random
from pathlib import Path
B = Path(__file__).resolve().parent
a = sys.argv[1:]; F1, F3 = (a + [None, None])[:2]
F1, F3 = F1 or "scored_v1_newjudge.jsonl", F3 or "scored_v3.jsonl"
STR = a[2:] or ["linear", "dynamic_graph"]
L = lambda p: [json.loads(l) for l in open(B / p, encoding="utf-8") if l.strip()]
SC = ("normal", "sparse", "flood", "noisy")
key = lambda r: (r["scenario"], json.dumps(r["topics"]), r["run"])
def unsup(r): j = r["judge"]; return 100 * j["claims_unsupported"] / j["claims_total"] if j.get("claims_total") else None
M = {"faithfulness": lambda r: r["judge"]["faithfulness"], "unsupported_claims_%": unsup,
     "coverage": lambda r: r["judge"]["coverage"], "conciseness": lambda r: r["judge"]["conciseness"]}
V1, V3 = L(F1), L(F3)
rnd = random.Random(0)
print(f"{'strategy':14}{'metric':24}{'pairs':>6}{'v1':>8}{'v3':>8}{'diff':>8}{'95% CI':>20}")
for s in STR:
    for n, f in M.items():
        d1 = {key(r): f(r) for r in V1 if r["strategy"] == s and r["scenario"] in SC and isinstance(r.get("judge"), dict)}
        d3 = {key(r): f(r) for r in V3 if r["strategy"] == s and r["scenario"] in SC and isinstance(r.get("judge"), dict)}
        ks = [k for k in d1 if k in d3 and d1[k] is not None and d3[k] is not None]
        if len(ks) < 5: continue
        d = [d3[k] - d1[k] for k in ks]; m = sum(d) / len(d)
        bs = sorted(sum(rnd.choice(d) for _ in d) / len(d) for _ in range(5000))
        print(f"{s:14}{n:24}{len(ks):>6}{sum(d1[k] for k in ks)/len(ks):>8.2f}{sum(d3[k] for k in ks)/len(ks):>8.2f}{m:>8.2f}{f'[{bs[125]:.2f}, {bs[4875]:.2f}]':>20}")