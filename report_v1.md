# Coordination Strategies Report (auto-generated)

- Files: results_corrected.jsonl (450 trials), scored_v1_newjudge.jsonl (360 judge-scored)
- Errored trials: 0
- ok = no error, briefing present, Key Takeaway, body <= 400 words. clean = ok and no junk URLs/text leaked.

## 1. Results by strategy (normal, sparse, flood, noisy)

| Metric | linear | static_graph | dynamic_graph |
|---|---|---|---|
| Success (ok), all scenarios shown | 120/120 | 119/120 | 114/120 |
| Clean (ok, no junk) | 118/120 | 117/120 | 87/120 |
| Success, normal | 30/30 | 29/30 | 28/30 |
| Success, sparse | 30/30 | 30/30 | 30/30 |
| Success, flood | 30/30 | 30/30 | 30/30 |
| Success, noisy | 30/30 | 30/30 | 26/30 |
| Median latency excl. backoff (s) | 5.98 | 6.37 | 18.39 |
| Mean LLM calls | 2 | 2 | 2.82 |
| Mean total tokens | 1411.48 | 1414.06 | 3474 |
| Cost per successful briefing (USD) | 0.00099 | 0.001 | 0.00246 |
| Judge relevance | 5 | 5 | 4.6 |
| Judge coverage | 5 | 4.99 | 4.74 |
| Judge faithfulness | 1.66 | 1.68 | 1.91 |
| Judge conciseness | 3.66 | 3.64 | 3.57 |
| Unsupported claims (judge) | 67.7% | 66.6% | 61.7% |
| Junk URLs leaked | 0 | 0 | 150 |
| Rate-limit hits | 26 | 27 | 2 |

## 2. By scenario

| Scenario | Strategy | Success | Median latency (s) | Mean tokens | Faithfulness | Junk leaked |
|---|---|---|---|---|---|---|
| normal | linear | 30/30 | 8.56 | 1468.93 | 1.57 | 0 |
| normal | static_graph | 29/30 | 9.38 | 1479.53 | 1.77 | 0 |
| normal | dynamic_graph | 28/30 | 25.58 | 4487.63 | 2.03 | 0 |
| sparse | linear | 30/30 | 6.01 | 935.73 | 1.67 | 0 |
| sparse | static_graph | 30/30 | 6.28 | 981.37 | 1.7 | 0 |
| sparse | dynamic_graph | 30/30 | 9.59 | 1632.97 | 1.8 | 0 |
| flood | linear | 30/30 | 9.98 | 1735.63 | 1.67 | 0 |
| flood | static_graph | 30/30 | 2.79 | 1732.47 | 1.63 | 0 |
| flood | dynamic_graph | 30/30 | 13.25 | 3542.27 | 1.97 | 0 |
| noisy | linear | 30/30 | 2.82 | 1505.63 | 1.73 | 0 |
| noisy | static_graph | 30/30 | 2.78 | 1462.87 | 1.63 | 0 |
| noisy | dynamic_graph | 26/30 | 21.21 | 4233.13 | 1.83 | 150 |
| apifail | linear | 0/30 | 0.74 | 274.1 | - | 0 |
| apifail | static_graph | 0/30 | 0.84 | 264.37 | - | 0 |
| apifail | dynamic_graph | 0/30 | 0.02 | 0 | - | 0 |

## 3. Failed trials (excluding apifail)

- static_graph | normal | ['AI'] | run 5 | 414 words | takeaway=True | error=None
- dynamic_graph | normal | ['cybersecurity'] | run 1 | 408 words | takeaway=True | error=None
- dynamic_graph | normal | ['cybersecurity'] | run 3 | 442 words | takeaway=True | error=None
- dynamic_graph | noisy | ['India tech startups'] | run 0 | 422 words | takeaway=True | error=None
- dynamic_graph | noisy | ['India tech startups'] | run 2 | 429 words | takeaway=True | error=None
- dynamic_graph | noisy | ['AI'] | run 3 | 433 words | takeaway=True | error=None
- dynamic_graph | noisy | ['cybersecurity'] | run 1 | 404 words | takeaway=True | error=None

## 4. Critic effect (34 revised trials with draft scores)

- faithfulness: draft 1.76 -> final 2.35
- coverage: draft 4.79 -> final 4.88
- conciseness: draft 3.74 -> final 3.68

## 5. Data checks

- stale `task_completed` != `ok`: 204 (use `ok`)
- latency outliers >60s (excl. backoff): 10; max 37133s -> report medians
- judge models used: ['qwen/qwen3.8-27b']
- verify PRICE_IN_PER_MILLION / PRICE_OUT_PER_MILLION against Groq's price sheet for the run date