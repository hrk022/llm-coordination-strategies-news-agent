# Coordination Strategies Report (auto-generated)

- Files: results_v3.jsonl (600 trials), scored_v3.jsonl (540 judge-scored)
- Errored trials: 0
- ok = no error, briefing present, Key Takeaway, body <= 400 words. clean = ok and no junk URLs/text leaked.

## 1. Results by strategy (normal, sparse, flood, noisy, transient)

| Metric | linear | critic_only | routing_only | dynamic_graph |
|---|---|---|---|---|
| Success (ok), all scenarios shown | 120/150 | 120/150 | 150/150 | 150/150 |
| Clean (ok, no junk) | 119/150 | 120/150 | 150/150 | 150/150 |
| Success, normal | 30/30 | 30/30 | 30/30 | 30/30 |
| Success, sparse | 30/30 | 30/30 | 30/30 | 30/30 |
| Success, flood | 30/30 | 30/30 | 30/30 | 30/30 |
| Success, noisy | 30/30 | 30/30 | 30/30 | 30/30 |
| Success, transient | 0/30 | 0/30 | 30/30 | 30/30 |
| Median latency excl. backoff (s) | 2.83 | 3.66 | 3.14 | 4.12 |
| Mean LLM calls | 1.8 | 2.61 | 1.8 | 2.84 |
| Mean total tokens | 1359.49 | 2032.29 | 1571.45 | 2518.21 |
| Cost per successful briefing (USD) | 0.00121 | 0.00174 | 0.00112 | 0.00173 |
| Judge relevance | 5 | 5 | 4.98 | 4.97 |
| Judge coverage | 5 | 5 | 5 | 5 |
| Judge faithfulness | 4.91 | 4.93 | 4.95 | 4.91 |
| Judge conciseness | 4.05 | 4.18 | 4.11 | 4.15 |
| Unsupported claims (judge) | 1.2% | 1.0% | 0.7% | 1.3% |
| Junk URLs leaked | 0 | 0 | 0 | 0 |
| Rate-limit hits | 0 | 33 | 12 | 32 |

## 2. By scenario

| Scenario | Strategy | Success | Median latency (s) | Mean tokens | Faithfulness | Junk leaked |
|---|---|---|---|---|---|---|
| normal | linear | 30/30 | 3.61 | 1843.57 | 4.9 | 0 |
| normal | critic_only | 30/30 | 4.14 | 2667.87 | 4.97 | 0 |
| normal | routing_only | 30/30 | 3.21 | 1694.37 | 4.93 | 0 |
| normal | dynamic_graph | 30/30 | 4.28 | 2689.47 | 4.97 | 0 |
| sparse | linear | 30/30 | 1.96 | 894.4 | 4.77 | 0 |
| sparse | critic_only | 30/30 | 2.81 | 1373.5 | 4.8 | 0 |
| sparse | routing_only | 30/30 | 1.46 | 619.9 | 4.9 | 0 |
| sparse | dynamic_graph | 30/30 | 2.18 | 1082.33 | 4.9 | 0 |
| flood | linear | 30/30 | 3.46 | 2034.57 | 4.97 | 0 |
| flood | critic_only | 30/30 | 4.4 | 3060.9 | 4.97 | 0 |
| flood | routing_only | 30/30 | 3.2 | 1958.03 | 5 | 0 |
| flood | dynamic_graph | 30/30 | 4.48 | 3156.27 | 4.97 | 0 |
| noisy | linear | 30/30 | 3.15 | 1745.43 | 5 | 0 |
| noisy | critic_only | 30/30 | 4.56 | 2785.8 | 5 | 0 |
| noisy | routing_only | 30/30 | 3.56 | 1793.57 | 4.97 | 0 |
| noisy | dynamic_graph | 30/30 | 4.18 | 2807.83 | 4.8 | 0 |
| transient | linear | 0/30 | 0.83 | 279.47 | - | 0 |
| transient | critic_only | 0/30 | 0.75 | 273.37 | - | 0 |
| transient | routing_only | 30/30 | 3.46 | 1791.4 | 4.97 | 0 |
| transient | dynamic_graph | 30/30 | 4.54 | 2855.17 | 4.93 | 0 |

## 3. Failed trials (excluding apifail)

- linear | transient | ['AI'] | run 0 | 10 words | takeaway=False | error=None
- critic_only | transient | ['AI'] | run 0 | 10 words | takeaway=False | error=None
- linear | transient | ['cybersecurity'] | run 0 | 10 words | takeaway=False | error=None
- critic_only | transient | ['cybersecurity'] | run 0 | 10 words | takeaway=False | error=None
- linear | transient | ['India tech startups'] | run 0 | 10 words | takeaway=False | error=None
- critic_only | transient | ['India tech startups'] | run 0 | 10 words | takeaway=False | error=None
- linear | transient | ['AI'] | run 1 | 10 words | takeaway=False | error=None
- critic_only | transient | ['AI'] | run 1 | 10 words | takeaway=False | error=None
- linear | transient | ['cybersecurity'] | run 1 | 10 words | takeaway=False | error=None
- critic_only | transient | ['cybersecurity'] | run 1 | 10 words | takeaway=False | error=None
- linear | transient | ['India tech startups'] | run 1 | 10 words | takeaway=False | error=None
- critic_only | transient | ['India tech startups'] | run 1 | 10 words | takeaway=False | error=None
- critic_only | transient | ['AI'] | run 2 | 10 words | takeaway=False | error=None
- linear | transient | ['cybersecurity'] | run 2 | 10 words | takeaway=False | error=None
- critic_only | transient | ['cybersecurity'] | run 2 | 10 words | takeaway=False | error=None
- linear | transient | ['India tech startups'] | run 2 | 10 words | takeaway=False | error=None
- critic_only | transient | ['India tech startups'] | run 2 | 10 words | takeaway=False | error=None
- linear | transient | ['AI'] | run 3 | 10 words | takeaway=False | error=None
- critic_only | transient | ['AI'] | run 3 | 10 words | takeaway=False | error=None
- linear | transient | ['cybersecurity'] | run 3 | 10 words | takeaway=False | error=None
- critic_only | transient | ['cybersecurity'] | run 3 | 10 words | takeaway=False | error=None
- linear | transient | ['India tech startups'] | run 3 | 10 words | takeaway=False | error=None
- critic_only | transient | ['India tech startups'] | run 3 | 10 words | takeaway=False | error=None
- linear | transient | ['AI'] | run 4 | 10 words | takeaway=False | error=None
- critic_only | transient | ['AI'] | run 4 | 10 words | takeaway=False | error=None
- linear | transient | ['cybersecurity'] | run 4 | 10 words | takeaway=False | error=None
- critic_only | transient | ['cybersecurity'] | run 4 | 10 words | takeaway=False | error=None
- linear | transient | ['India tech startups'] | run 4 | 10 words | takeaway=False | error=None
- critic_only | transient | ['India tech startups'] | run 4 | 10 words | takeaway=False | error=None
- linear | transient | ['AI'] | run 5 | 10 words | takeaway=False | error=None
- critic_only | transient | ['AI'] | run 5 | 10 words | takeaway=False | error=None
- linear | transient | ['cybersecurity'] | run 5 | 10 words | takeaway=False | error=None
- critic_only | transient | ['cybersecurity'] | run 5 | 10 words | takeaway=False | error=None
- linear | transient | ['India tech startups'] | run 5 | 10 words | takeaway=False | error=None
- critic_only | transient | ['India tech startups'] | run 5 | 10 words | takeaway=False | error=None
- linear | transient | ['AI'] | run 6 | 10 words | takeaway=False | error=None
- critic_only | transient | ['AI'] | run 6 | 10 words | takeaway=False | error=None
- linear | transient | ['cybersecurity'] | run 6 | 10 words | takeaway=False | error=None
- critic_only | transient | ['cybersecurity'] | run 6 | 10 words | takeaway=False | error=None
- linear | transient | ['India tech startups'] | run 6 | 10 words | takeaway=False | error=None
- critic_only | transient | ['India tech startups'] | run 6 | 10 words | takeaway=False | error=None
- linear | transient | ['AI'] | run 7 | 10 words | takeaway=False | error=None
- critic_only | transient | ['AI'] | run 7 | 10 words | takeaway=False | error=None
- linear | transient | ['cybersecurity'] | run 7 | 10 words | takeaway=False | error=None
- critic_only | transient | ['cybersecurity'] | run 7 | 10 words | takeaway=False | error=None
- linear | transient | ['India tech startups'] | run 7 | 10 words | takeaway=False | error=None
- critic_only | transient | ['India tech startups'] | run 7 | 10 words | takeaway=False | error=None
- linear | transient | ['AI'] | run 8 | 10 words | takeaway=False | error=None
- critic_only | transient | ['AI'] | run 8 | 10 words | takeaway=False | error=None
- linear | transient | ['cybersecurity'] | run 8 | 10 words | takeaway=False | error=None
- critic_only | transient | ['cybersecurity'] | run 8 | 10 words | takeaway=False | error=None
- linear | transient | ['India tech startups'] | run 8 | 10 words | takeaway=False | error=None
- critic_only | transient | ['India tech startups'] | run 8 | 10 words | takeaway=False | error=None
- linear | transient | ['AI'] | run 9 | 10 words | takeaway=False | error=None
- critic_only | transient | ['AI'] | run 9 | 10 words | takeaway=False | error=None
- linear | transient | ['cybersecurity'] | run 9 | 10 words | takeaway=False | error=None
- critic_only | transient | ['cybersecurity'] | run 9 | 10 words | takeaway=False | error=None
- linear | transient | ['India tech startups'] | run 9 | 10 words | takeaway=False | error=None
- critic_only | transient | ['India tech startups'] | run 9 | 10 words | takeaway=False | error=None
- linear | transient | ['AI'] | run 2 | 10 words | takeaway=False | error=None

## 4. Critic effect (4 revised trials with draft scores)

- faithfulness: draft 4.5 -> final 4.75
- coverage: draft 5 -> final 5
- conciseness: draft 3.75 -> final 4.25

## 5. Data checks

- stale `task_completed` != `ok`: 0 (use `ok`)
- latency outliers >60s (excl. backoff): 0; max 12s -> report medians
- judge models used: ['qwen/qwen3.8-27b']
- verify PRICE_IN_PER_MILLION / PRICE_OUT_PER_MILLION against Groq's price sheet for the run date