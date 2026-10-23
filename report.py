"""report.py - offline report. Usage:  python report.py [results.jsonl] [scored.jsonl]
Defaults: results_corrected.jsonl scored_corrected.jsonl. Strategies/scenarios are read from the data.
Uses `ok` (revalidated flag), never the stale `task_completed`."""
import json, sys, statistics as st
from pathlib import Path

B = Path(__file__).resolve().parent
RF, SF = (sys.argv + [None, None])[1:3]
RF, SF = RF or "results_corrected.jsonl", SF or "scored_corrected.jsonl"
L = lambda p: [json.loads(l) for l in open(B / p, encoding="utf-8") if l.strip()] if (B / p).exists() else []
R, S = L(RF), L(SF)
ORDER = ["linear", "static_graph", "critic_only", "routing_only", "dynamic_graph"]
ST_ = [s for s in ORDER if any(r["strategy"] == s for r in R)]
SC = [s for s in ("normal", "sparse", "flood", "noisy", "transient", "apifail") if any(r["scenario"] == s for r in R)]
NA = [s for s in SC if s != "apifail"]
mean = lambda v: round(st.mean(v), 2) if v else "n/a"
med = lambda v: round(st.median(v), 2) if v else "n/a"
sel = lambda rows, s=None, sc=None: [r for r in rows if (s is None or r["strategy"] == s) and (sc is None or r["scenario"] in sc)]
clean = lambda r: bool(r["ok"] and not r.get("junk_leaked") and not r.get("junk_in_text"))
frac = lambda rows, k="ok": f"{sum(clean(r) if k == 'clean' else bool(r.get(k)) for r in rows)}/{len(rows)}"
J = lambda rows, k: [r["judge"][k] for r in rows if isinstance(r.get("judge"), dict) and r["judge"].get(k) is not None]

def unsup(rows):
    j = [r["judge"] for r in rows if isinstance(r.get("judge"), dict)]
    t = sum(x["claims_total"] for x in j)
    return f"{100 * sum(x['claims_unsupported'] for x in j) / t:.1f}%" if t else "n/a"

def table(title, header, rows):
    return [f"\n## {title}\n", "| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]

out = ["# Coordination Strategies Report (auto-generated)\n", f"- Files: {RF} ({len(R)} trials), {SF} ({len(S)} judge-scored)",
       f"- Errored trials: {sum(bool(r.get('error')) for r in R)}",
       "- ok = no error, briefing present, Key Takeaway, body <= 400 words. clean = ok and no junk URLs/text leaked."]
na = lambda s: sel(R, s, NA)
sc_ = lambda s: sel(S, s, NA)
M = [("Success (ok), all scenarios shown", lambda s: frac(na(s))),
     ("Clean (ok, no junk)", lambda s: frac(na(s), "clean")),
     *[(f"Success, {c}", (lambda c: lambda s: frac(sel(R, s, (c,))))(c)) for c in NA],
     ("Median latency excl. backoff (s)", lambda s: med([r["latency_excluding_backoff_s"] for r in na(s)])),
     ("Mean LLM calls", lambda s: mean([r["llm_calls"] for r in na(s)])),
     ("Mean total tokens", lambda s: mean([r["total_tokens"] for r in na(s)])),
     ("Cost per successful briefing (USD)", lambda s: round(sum(r["estimated_cost_usd"] for r in na(s)) / max(1, sum(bool(r["ok"]) for r in na(s))), 5)),
     ("Judge relevance", lambda s: mean(J(sc_(s), "relevance"))), ("Judge coverage", lambda s: mean(J(sc_(s), "coverage"))),
     ("Judge faithfulness", lambda s: mean(J(sc_(s), "faithfulness"))), ("Judge conciseness", lambda s: mean(J(sc_(s), "conciseness"))),
     ("Unsupported claims (judge)", lambda s: unsup(sc_(s))),
     ("Junk URLs leaked", lambda s: sum(r.get("junk_leaked") or 0 for r in na(s))),
     ("Rate-limit hits", lambda s: sum(r["rate_limited"] for r in sel(R, s)))]
out += table(f"1. Results by strategy ({', '.join(NA)})", ["Metric", *ST_], [[n, *[f(s) for s in ST_]] for n, f in M])
out += table("2. By scenario", ["Scenario", "Strategy", "Success", "Median latency (s)", "Mean tokens", "Faithfulness", "Junk leaked"],
             [[sc, s, frac(sel(R, s, (sc,))), med([r["latency_excluding_backoff_s"] for r in sel(R, s, (sc,))]),
               mean([r["total_tokens"] for r in sel(R, s, (sc,))]), mean(J(sel(S, s, (sc,)), "faithfulness")) if sel(S, s, (sc,)) else "-",
               sum(r.get("junk_leaked") or 0 for r in sel(R, s, (sc,)))] for sc in SC for s in ST_])
bad = [r for r in R if not r["ok"] and r["scenario"] != "apifail"]
out += ["\n## 3. Failed trials (excluding apifail)\n"] + ([f"- {r['strategy']} | {r['scenario']} | {r['topics']} | run {r['run']} | {r['words']} words | takeaway={r['has_takeaway']} | error={r['error']}" for r in bad] or ["- none"])
d = [r for r in S if isinstance(r.get("judge_draft"), dict)]
out += [f"\n## 4. Critic effect ({len(d)} revised trials with draft scores)\n"] + (
    [f"- {k}: draft {mean([r['judge_draft'][k] for r in d])} -> final {mean([r['judge'][k] for r in d])}" for k in ("faithfulness", "coverage", "conciseness")] if d else ["- no draft scores saved"])
out += ["\n## 5. Data checks\n",
        f"- stale `task_completed` != `ok`: {sum(bool(r['ok']) != bool(r.get('task_completed', r['ok'])) for r in R)} (use `ok`)",
        f"- latency outliers >60s (excl. backoff): {sum(r['latency_excluding_backoff_s'] > 60 for r in R)}; max {max((r['latency_excluding_backoff_s'] for r in R), default=0):.0f}s -> report medians",
        f"- judge models used: {sorted({r.get('judge_model', 'not recorded (default = generator model)') for r in S})}",
        "- verify PRICE_IN_PER_MILLION / PRICE_OUT_PER_MILLION against Groq's price sheet for the run date"]
(B / "report.md").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out)); print("\nSaved:", B / "report.md")