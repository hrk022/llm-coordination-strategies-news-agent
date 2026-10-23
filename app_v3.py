import os, re, json, time
import httpx
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import TypedDict, List, Optional
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
import gradio as gr
import resend

load_dotenv()

IST       = ZoneInfo("Asia/Kolkata")
llm       = ChatGroq(api_key=os.environ.get("GROQ_API_KEY"), model_name="openai/gpt-oss-120b", temperature=0.3, timeout=90, max_retries=0)
scheduler = BackgroundScheduler(timezone=IST)
scheduler.start()

TOO_FEW  = 3
TOO_MANY = 15
STRATEGY = os.environ.get("STRATEGY", "dynamic_graph")  # linear | static_graph | dynamic_graph
# Backward-compatible aliases for an existing .env file.
STRATEGY = {"seq": "linear", "graph": "dynamic_graph", "graph_nc": "static_graph",
            "hier": "static_graph"}.get(STRATEGY, STRATEGY)

# ── Experiment config ─────────────────────────────────────────────────────────
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "openai/gpt-oss-120b")   # different family from the generator
judge_llm   = ChatGroq(api_key=os.environ.get("GROQ_API_KEY"), model_name=JUDGE_MODEL, temperature=0, timeout=90, max_retries=0)
# Configure prices for the generator model (USD per 1M tokens). Verify against the
# current provider price sheet before reporting cost in a paper.
PRICE_IN  = float(os.environ.get("PRICE_IN_PER_MILLION", "0.59"))
PRICE_OUT = float(os.environ.get("PRICE_OUT_PER_MILLION", "0.79"))
PAUSE       = float(os.environ.get("PAUSE", 1))  # seconds between trials (free-tier rate limits)
CACHE_FILE  = "gnews_cache.json"                 # frozen GNews results, persisted so every strategy/run sees identical articles
CACHE       = json.load(open(CACHE_FILE, encoding="utf-8")) if os.path.exists(CACHE_FILE) else {}
METRICS     = []                                 # one entry per LLM call
CNT         = {"gnews": 0, "filter_fail": 0, "loops": 0, "retries": 0, "rate_limited": 0, "wait": 0.0}
EXTRA       = {"draft": "", "headlines": []}     # first draft + final headlines, saved per trial
SCENARIO    = "normal"                           # normal | sparse | flood | noisy | apifail | transient (simulated stress tests)
JUNK        = [f"Unrelated local story #{i}: council debates parking rules" for i in range(20)]

def invoke_retry(model, msgs, tries=5):
    """Invoke with exponential backoff; backoff is included in end-to-end latency."""
    for i in range(tries):
        try:
            return model.invoke(msgs)
        except Exception as e:
            if any(k in str(e).lower() for k in ("429", "rate", "connection", "timed out", "timeout", "503", "capacity", "overloaded", "unavailable")):
                print(f"429 (try {i+1}/{tries}), waiting {5 * 2 ** i}s: {str(e)[:200]}", flush=True)
                CNT["rate_limited"] += 1; w = 5 * 2 ** i; CNT["wait"] += w; time.sleep(w); continue
            raise
    raise RuntimeError("rate limit: retries exhausted")

def usage_from_response(response):
    """Extract token usage across common LangChain/Groq metadata shapes."""
    usage = response.response_metadata.get("token_usage") or {}
    if not usage:
        usage = response.usage_metadata or {}
    input_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0
    output_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
    return int(input_tokens), int(output_tokens)


def call(msgs, agent):
    """Meter one generator-strategy LLM call, including token usage and call latency."""
    t = time.time()
    r = invoke_retry(llm, msgs)
    input_tokens, output_tokens = usage_from_response(r)
    METRICS.append({"agent": agent, "input_tokens": input_tokens,
                    "output_tokens": output_tokens, "latency_s": round(time.time() - t, 3)})
    return r

def perturb(headlines, sources, attempt=0):
    """Inject the robustness scenario after the (cached) scrape."""
    if SCENARIO == "sparse":  return headlines[:2], sources[:2]
    if SCENARIO == "apifail": return [], []
    if SCENARIO == "transient" and attempt == 0: return [], []   # API fails once, recovers on retry
    if SCENARIO in ("noisy", "flood"):
        junk = JUNK[:5] if SCENARIO == "noisy" else JUNK
        return headlines + junk, sources + [{"title": j, "url": f"https://junk.example/{i}"} for i, j in enumerate(junk)]
    return headlines, sources


class State(TypedDict):
    topics:       List[str]
    email:        Optional[str]
    headlines:    List[str]
    sources:      List[dict]
    briefing:     str
    retry_count:  int
    quality_note: str
    verdict:      str     # critic output (graph strategy)
    revisions:    int     # critic passes so far (graph strategy)
    draft:        str     # first draft, kept to measure whether the critic loop helps

def blank(topics, email=None) -> State:
    return {"topics": topics, "email": email, "headlines": [], "sources": [], "briefing": "",
            "retry_count": 0, "quality_note": "", "verdict": "", "revisions": 0, "draft": ""}


# ── Agents ────────────────────────────────────────────────────────────────────
def scrape_news(state: State) -> State:
    query = " ".join(state["topics"])
    if state.get("retry_count", 0) > 0:
        query = " ".join(state["topics"][0].split()[:2])
        print(f"Retrying with broader query: {query}")

    if query in CACHE:
        headlines, sources = CACHE[query]
    else:
        headlines, sources = [], []
        try:
            CNT["gnews"] += 1
            r = httpx.get("https://gnews.io/api/v4/search", params={
                "q": query, "token": os.environ.get("GNEWS_API_KEY"),
                "lang": "en", "max": 20, "sortby": "publishedAt",
            }, timeout=10)
            for a in r.json().get("articles", []):
                title = a.get("title", "").strip()
                link  = a.get("url", "").strip()
                if title:
                    headlines.append(title)
                    sources.append({"title": title, "url": link})
            if headlines:
                CACHE[query] = (headlines, sources)
                with open(CACHE_FILE, "w", encoding="utf-8") as f: json.dump(CACHE, f, ensure_ascii=False)
        except Exception as e:
            print(f"GNews error: {e}")

    state["headlines"], state["sources"] = perturb(list(headlines), list(sources), state.get("retry_count", 0))
    return state


def evaluate(state: State) -> State:
    count = len(state["headlines"])
    if count < TOO_FEW:
        state["quality_note"] = f"⚠️ Only {count} articles found — retrying with broader query..."
    elif count > TOO_MANY:
        state["quality_note"] = f"📊 {count} articles found — filtering most relevant ones..."
    else:
        state["quality_note"] = f"✅ {count} articles found — generating briefing..."
    print(state["quality_note"])
    return state


def filter_articles(state: State) -> State:
    headlines, sources, topics = state["headlines"], state["sources"], state["topics"]
    resp = call([
        SystemMessage(content=(
            f"You are a news relevance filter. Topics of interest: {', '.join(topics)}.\n"
            f"From the list below, return ONLY the indices (0-based, comma separated) of the "
            f"top {TOO_FEW} to {TOO_MANY} most relevant and diverse articles. "
            "Return ONLY numbers like: 0,2,5,7,11 — nothing else."
        )),
        HumanMessage(content="\n".join(f"{i}. {h}" for i, h in enumerate(headlines)))
    ], "filter")

    try:
        indices = [int(x.strip()) for x in resp.content.strip().split(",") if x.strip().isdigit()]
        indices = [i for i in indices if i < len(headlines)]
        if not indices:
            raise ValueError("filter returned no valid indices")   # keep all headlines instead of wiping them
        state["headlines"] = [headlines[i] for i in indices]
        state["sources"]   = [sources[i] for i in indices]
        print(f"Filtered to {len(state['headlines'])} articles")
    except Exception as e:
        CNT["filter_fail"] += 1
        print(f"Filter error: {e}")
    return state


def generate_briefing(state: State) -> State:
    if not state["headlines"]:
        state["briefing"] = "No news found even after retrying. Please try different keywords."
        return state

    bullets  = "\n".join(f"- {h}" for h in state["headlines"])
    feedback = f"\n\nFix this reviewer issue: {state['verdict']}" if state.get("revisions") else ""
    resp = call([
        SystemMessage(content=(
            f"You are a news briefing assistant. Today is {datetime.now(IST).strftime('%B %d, %Y')}.\n"
            "Write a clean briefing from these headlines. Group by sub-topic. Use ONLY facts stated in the "
            "headlines: add no background, numbers, names, dates or causes that are not in them. "
            "End with a 2-line Key Takeaway built only from the headlines. Keep it under 350 words."
        )),
        HumanMessage(content=f"Topics: {', '.join(state['topics'])}\n\nHeadlines:\n{bullets}{feedback}")
    ], "writer")

    sources_text = "\n\n---\n📚 **Sources:**\n" + "\n".join(
        f"- {s['title']} → {s['url']}" for s in state.get("sources", []) if s.get("url")
    )
    state["briefing"] = resp.content + sources_text
    return state


def critic(state: State) -> State:
    if not state.get("revisions"):
        state["draft"] = state["briefing"]
    if not state["headlines"]:
        state["verdict"] = "PASS"
    else:
        r = call([
            SystemMessage(content="Check the briefing against the headlines. Reply PASS, or FAIL: <reason> "
                                  "if it has unsupported claims or misses key topics."),
            HumanMessage(content="Headlines:\n" + "\n".join(state["headlines"]) + "\n\nBriefing:\n" + state["briefing"])
        ], "critic")
        state["verdict"] = r.content.strip()
    state["revisions"] = state.get("revisions", 0) + 1
    return state


# ── Coordination strategy implementations ────────────────────────────────────
# linear: fixed sequential function calls
# static_graph: fixed LangGraph path; every node runs in the same order
# dynamic_graph: conditional retry/filter routing plus a critic-revision loop

def route_after_evaluate(state: State) -> str:
    count = len(state["headlines"])
    if count < TOO_FEW and state.get("retry_count", 0) < 2:
        return "retry"
    if count > TOO_MANY:
        return "filter"
    return "brief"


def route_after_critic(state: State) -> str:
    return "brief" if state["verdict"].startswith("FAIL") and state["revisions"] < 2 else END


def route_after_evaluate_v3(state: State) -> str:
    """Retry sparse results; otherwise ALWAYS filter (the old route skipped filtering at <=15 headlines)."""
    count = len(state["headlines"])
    if count < TOO_FEW:
        return "retry" if state.get("retry_count", 0) < 2 else "brief"
    return "filter"


MAX_REV = int(os.environ.get("MAX_REV", 3))   # critic passes; a length failure can need a second revision


def critic_v3(state: State) -> State:
    """Original critic plus a deterministic length check (no extra LLM call)."""
    state = critic(state)
    n = len(briefing_body(state["briefing"]).split())
    if n > 400:
        note = f"shorten the briefing body from {n} to under 350 words"
        state["verdict"] = ("FAIL: " + note) if not state["verdict"].upper().startswith("FAIL") else state["verdict"] + "; " + note
    return state


def route_after_critic_v3(state: State) -> str:
    return "brief" if state["verdict"].upper().startswith("FAIL") and state["revisions"] < MAX_REV else END


def increment_retry(state: State) -> State:
    state["retry_count"] = state.get("retry_count", 0) + 1
    return state


def build_static_graph():
    """A deterministic graph: no conditional edges, retries, or critic loop."""
    g = StateGraph(State)
    g.add_node("scrape", scrape_news)
    g.add_node("evaluate", evaluate)
    g.add_node("filter", filter_articles)
    g.add_node("brief", generate_briefing)
    g.set_entry_point("scrape")
    g.add_edge("scrape", "evaluate")
    g.add_edge("evaluate", "filter")
    g.add_edge("filter", "brief")
    g.add_edge("brief", END)
    return g.compile()


def build_dynamic_graph():
    """Adaptive graph: route based on article count, retry sparse results, and critic loop."""
    g = StateGraph(State)
    g.add_node("scrape", scrape_news)
    g.add_node("evaluate", evaluate)
    g.add_node("retry", increment_retry)
    g.add_node("filter", filter_articles)
    g.add_node("brief", generate_briefing)
    g.add_node("critic", critic)
    g.set_entry_point("scrape")
    g.add_edge("scrape", "evaluate")
    g.add_edge("retry", "scrape")
    g.add_edge("filter", "brief")
    g.add_conditional_edges("evaluate", route_after_evaluate,
                            {"retry": "retry", "filter": "filter", "brief": "brief"})
    g.add_edge("brief", "critic")
    g.add_conditional_edges("critic", route_after_critic, {"brief": "brief", END: END})
    return g.compile()


def _graph_runner(compiled_graph):
    def run(topics):
        result = compiled_graph.invoke(blank(topics))
        CNT["loops"] = result["revisions"]
        CNT["retries"] = result["retry_count"]
        EXTRA.update(draft=result["draft"], headlines=result["headlines"])
        return result["briefing"]
    return run


def run_linear(topics):
    state = blank(topics)
    for step in (scrape_news, filter_articles, generate_briefing):
        state = step(state)
    EXTRA.update(draft=state["draft"], headlines=state["headlines"])
    return state["briefing"]


def build_graph_v3(adaptive=True, critic_loop=True):
    """adaptive: retry/filter routing. critic_loop: critic + bounded revisions. Both False == static graph."""
    g = StateGraph(State)
    for name, fn in (("scrape", scrape_news), ("evaluate", evaluate), ("retry", increment_retry),
                     ("filter", filter_articles), ("brief", generate_briefing)):
        g.add_node(name, fn)
    g.set_entry_point("scrape")
    g.add_edge("scrape", "evaluate"); g.add_edge("retry", "scrape"); g.add_edge("filter", "brief")
    if adaptive:
        g.add_conditional_edges("evaluate", route_after_evaluate_v3, {"retry": "retry", "filter": "filter", "brief": "brief"})
    else:
        g.add_edge("evaluate", "filter")
    if critic_loop:
        g.add_node("critic", critic_v3)
        g.add_edge("brief", "critic")
        g.add_conditional_edges("critic", route_after_critic_v3, {"brief": "brief", END: END})
    else:
        g.add_edge("brief", END)
    return g.compile()


static_graph_runner = _graph_runner(build_static_graph())
dynamic_graph_runner = _graph_runner(build_graph_v3(True, True))   # v3: always-filter routing + critic
RUNNERS = {
    "linear": run_linear,
    "static_graph": static_graph_runner,
    "dynamic_graph": dynamic_graph_runner,
    "critic_only": _graph_runner(build_graph_v3(False, True)),     # ablation: critic loop, no adaptive routing
    "routing_only": _graph_runner(build_graph_v3(True, False)),    # ablation: adaptive routing, no critic
}


# ── Experiment harness ────────────────────────────────────────────────────────
def briefing_body(b: str) -> str:
    """Return the briefing text before the final Sources section, not before internal dividers."""
    return re.split(
        r"\n\s*---\s*\n(?=\s*📚\s*\*\*Sources:\*\*)",
        b or "",
        maxsplit=1,
    )[0]

def rules(b: str) -> dict:
    body = briefing_body(b)
    w = len(body.split())
    return {"words": w, "under_400": w <= 400, "has_takeaway": "takeaway" in body.lower(),
            "n_sources": b.count("→ http"), "junk_leaked": b.count("junk.example"),   # junk that survived into the sources
            "junk_in_text": body.lower().count("parking")}                           # junk topic mentioned in the prose

def run_trial(strategy, topics, scenario="normal"):
    global SCENARIO
    SCENARIO = scenario
    METRICS.clear(); CNT.update(gnews=0, filter_fail=0, loops=0, retries=0, rate_limited=0, wait=0.0)
    EXTRA.update(draft="", headlines=[])
    t, err, out = time.time(), None, ""
    try:
        out = RUNNERS[strategy](topics)
    except Exception as e:
        err = str(e)
    wall_latency = round(time.time() - t, 3)  # includes rate-limit backoff
    tin = sum(m["input_tokens"] for m in METRICS)
    tout = sum(m["output_tokens"] for m in METRICS)
    body = briefing_body(out) if out else ""
    ok = (err is None and bool(body.strip())
          and not body.startswith("No news found")
          and "takeaway" in body.lower() and len(body.split()) <= 400)
    cost = (tin * PRICE_IN + tout * PRICE_OUT) / 1e6
    return {"strategy": strategy, "scenario": scenario, "topics": topics,
            "ok": ok, "task_completed": ok, "error": err,
            "latency_s": wall_latency, "latency_excluding_backoff_s": round(max(0, wall_latency - CNT["wait"]), 3),
            "llm_calls": len(METRICS), "input_tokens": tin, "output_tokens": tout,
            "total_tokens": tin + tout, "estimated_cost_usd": round(cost, 8),
            "cost_per_successful_briefing_usd": round(cost, 8) if ok else None,
            "agents": list(METRICS), **{k: v for k, v in CNT.items() if k != "wait"},
            "backoff_wait_s": round(CNT["wait"], 3), **rules(out),
            "clean": bool(ok and not rules(out)["junk_leaked"] and not rules(out)["junk_in_text"]),
            "headlines": list(EXTRA["headlines"]), "draft": EXTRA["draft"], "briefing": out}

def done_keys(path):
    if not os.path.exists(path): return set()
    return {json.dumps([r["strategy"], r["scenario"], r["topics"], r["run"]]) for r in map(json.loads, open(path, encoding="utf-8"))}

def experiment(topic_sets, n=10, scenarios=("normal", "sparse", "flood", "noisy", "transient"), out="results_v3.jsonl",
               strategies=("linear", "dynamic_graph", "critic_only", "routing_only")):
    """Resumable. Strategies are interleaved per (run, scenario, topic) so rate limits hit them equally."""
    global SCENARIO
    done = done_keys(out)
    with open(out, "a", encoding="utf-8") as f:
        for i in range(n):
            for sc in scenarios:
                for topics in topic_sets:
                    for strat in strategies:
                        if json.dumps([strat, sc, topics, i]) in done: continue
                        f.write(json.dumps({**run_trial(strat, topics, sc), "run": i}, ensure_ascii=False) + "\n"); f.flush()
                        print(f"saved: {strat} | {sc} | {topics} | run {i}", flush=True)
                        time.sleep(PAUSE)
    SCENARIO = "normal"



def judge(topics, headlines, briefing, usage_log=None):
    if not briefing or briefing.startswith("No news found"):
        print(
            f"JUDGE SKIP: briefing is empty or unavailable. "
            f"Briefing preview: {str(briefing)[:200]!r}",
           flush=True,
           )
        return None

    try:
        r = invoke_retry(
            judge_llm,
            [
                SystemMessage(
                    content=(
                        "You are a strict news-briefing evaluator. Given topics, "
                        "the source headlines and a briefing, return ONLY JSON:\n"
                        '{"relevance":1-5,"coverage":1-5,"faithfulness":1-5,'
                        '"conciseness":1-5,"claims_total":int,'
                        '"claims_unsupported":int}\n'
                        "relevance = on-topic; coverage = captures the important "
                        "headlines; faithfulness = every claim is supported by "
                        "the headlines (5 = nothing invented); conciseness = "
                        "tight, no padding. claims_total = factual claims in the "
                        "briefing; claims_unsupported = those NOT supported by "
                        "the headlines."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Topics: {', '.join(topics)}\n\nHeadlines:\n"
                        + "\n".join(headlines)
                        + "\n\nBriefing:\n"
                        + briefing_body(briefing)
                    )
                ),
            ],
        )

        input_tokens, output_tokens = usage_from_response(r)

        if usage_log is not None:
            usage_log.append({
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            })

        match = re.search(r"\{.*\}", r.content, re.S)

        if not match:
            print(
                "JUDGE ERROR: Model returned no JSON object. "
                f"Response: {r.content[:500]!r}",
                flush=True,
            )
            return None

        result = json.loads(match.group(0))

        required = [
            "relevance",
            "coverage",
            "faithfulness",
            "conciseness",
            "claims_total",
            "claims_unsupported",
        ]

        missing = [key for key in required if key not in result]
        if missing:
            print(
                f"JUDGE ERROR: Missing JSON fields: {missing}. "
                f"Parsed result: {result!r}",
                flush=True,
            )
            return None

        return result

    except Exception as e:
        print(f"\nJUDGE ERROR TYPE: {type(e).__name__}", flush=True)
        print(f"JUDGE ERROR DETAILS: {e!r}", flush=True)
        import traceback
        traceback.print_exc()
        return None



def score_results(src="results.jsonl", dst="scored.jsonl"):
    """Score experiment trials, save immediately, and safely resume."""
    import os
    import json
    import time

    def trial_key(row):
        return json.dumps(
            [
                row["strategy"],
                row["scenario"],
                row["topics"],
                row["run"],
            ],
            sort_keys=True,
        )

    def has_valid_score(row):
        judge_data = row.get("judge")
        return (
            isinstance(judge_data, dict)
            and all(
                judge_data.get(field) is not None
                for field in ("relevance", "coverage", "faithfulness")
            )
        )

    def load_records(path):
        records = {}

        if not os.path.exists(path):
            return records

        with open(path, "r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                if not line.strip():
                    continue

                try:
                    row = json.loads(line)
                    records[trial_key(row)] = row
                except (json.JSONDecodeError, KeyError, TypeError):
                    print(
                        f"Warning: skipping invalid record "
                        f"at {path}:{line_number}"
                    )

        return records

    def save_records(records):
        # Write to a temporary file, then replace the output atomically.
        temp_path = dst + ".tmp"

        with open(temp_path, "w", encoding="utf-8") as f:
            for record in records.values():
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, dst)

    if not os.path.exists(src):
        raise FileNotFoundError(f"Scoring source file not found: {src}")

    repair_only = os.environ.get("SCORE_REPAIR_ONLY") == "1"
    pause = max(float(os.environ.get("PAUSE", "1")), 1.0)
    failure_pause = max(
        float(os.environ.get("SCORE_FAILURE_PAUSE", "30")),
        5.0,
    )

    existing = load_records(dst)

    with open(src, "r", encoding="utf-8") as f:
        source_rows = [
            json.loads(line)
            for line in f
            if line.strip()
        ]

    # Repair-only mode revisits only trials already present in the output.
    if repair_only:
        source_rows = [
            row for row in source_rows
            if trial_key(row) in existing
        ]

    total = len(source_rows)
    attempted = 0
    failed_this_run = 0
    succeeded_this_run = 0
    skipped = 0

    def print_progress(index):
        scored = sum(
            has_valid_score(record)
            for record in existing.values()
        )
        failed = failed_this_run
        remaining = max(total - index, 0)

        print(
            f"Progress: {index}/{total} attempted "
            f"| {scored} scored "
            f"| {failed} failed this run "
            f"| {remaining} remaining",
            flush=True,
        )

    print(f"Source trials: {total}")
    print(f"Existing records: {len(existing)}")
    print(
        "Already-valid scores: "
        f"{sum(has_valid_score(r) for r in existing.values())}"
    )
    print("Starting scoring...\n", flush=True)

    for index, row in enumerate(source_rows, start=1):
        k = trial_key(row)
        old = existing.get(k, {})

        # Don't spend API calls on trials with valid saved scores.
        if has_valid_score(old):
            skipped += 1
            print(
                f"[{index}/{total}] SKIPPED — valid score exists",
                flush=True,
            )
            print_progress(index)
            continue

        attempted += 1
        new_row = {**row, **old}
        judge_metrics = []

        # Correctly indented error handling with diagnostic output.
        try:
            judge_result = judge(
                row["topics"],
                row["headlines"],
                row["briefing"],
                judge_metrics,
            )
        except Exception as exc:
            print(
                f"JUDGE ERROR TYPE: {type(exc).__name__}",
                flush=True,
            )
            print(
                f"JUDGE ERROR DETAILS: {exc!r}",
                flush=True,
            )
            judge_result = None

        if judge_result is None:
            print(
                "DEBUG: judge() returned None. "
                "The error may have been caught inside judge().",
                flush=True,
            )

        valid_result = (
            isinstance(judge_result, dict)
            and all(
                judge_result.get(field) is not None
                for field in ("relevance", "coverage", "faithfulness")
            )
        )

        if not valid_result:
            failed_this_run += 1
            print(
                f"[{index}/{total}] FAILED — no valid judge score",
                flush=True,
            )
            print_progress(index)
            print(
                f"Pausing {failure_pause:.0f}s before the next trial.",
                flush=True,
            )
            time.sleep(failure_pause)
            continue

        # Save the successful score immediately.
        new_row["judge"] = judge_result
        new_row["judge_model"] = JUDGE_MODEL
        new_row["judge_usage"] = {
            "calls": len(judge_metrics),
            "input_tokens": sum(
                m.get("input_tokens", 0) for m in judge_metrics
            ),
            "output_tokens": sum(
                m.get("output_tokens", 0) for m in judge_metrics
            ),
            "total_tokens": sum(
                m.get("input_tokens", 0)
                + m.get("output_tokens", 0)
                for m in judge_metrics
            ),
        }

        existing[k] = new_row
        save_records(existing)
        succeeded_this_run += 1

        print(
            f"[{index}/{total}] SAVED — "
            f"{row['strategy']} | {row['scenario']} | "
            f"run {row['run']}",
            flush=True,
        )

        # Preserve optional draft scoring, if applicable.
        if row.get("draft") and row.get("loops", 0) > 1:
            draft_metrics = []

            try:
                draft_score = judge(
                    row["topics"],
                    row["headlines"],
                    row["draft"],
                    draft_metrics,
                )

                if isinstance(draft_score, dict):
                    new_row["judge_draft"] = draft_score

                    usage = new_row["judge_usage"]
                    usage["calls"] += len(draft_metrics)
                    usage["input_tokens"] += sum(
                        m.get("input_tokens", 0)
                        for m in draft_metrics
                    )
                    usage["output_tokens"] += sum(
                        m.get("output_tokens", 0)
                        for m in draft_metrics
                    )
                    usage["total_tokens"] += sum(
                        m.get("input_tokens", 0)
                        + m.get("output_tokens", 0)
                        for m in draft_metrics
                    )

                    existing[k] = new_row
                    save_records(existing)

            except Exception as exc:
                print(
                    f"Optional draft judging failed: {exc}",
                    flush=True,
                )

        print_progress(index)
        time.sleep(pause)

    valid_final = sum(
        has_valid_score(record)
        for record in existing.values()
    )

    print("\n========== SCORING SUMMARY ==========")
    print(f"Source trials processed: {total}")
    print(f"Trials attempted this run: {attempted}")
    print(f"Already-scored trials skipped: {skipped}")
    print(f"New valid scores saved: {succeeded_this_run}")
    print(f"Failed scoring attempts: {failed_this_run}")
    print(f"Total records in output: {len(existing)}")
    print(f"Total valid scores saved: {valid_final}")
    print(f"Output file: {dst}")


def summarize_results(src="scored.jsonl", dst="summary.json"):
    """Aggregate the paper metrics by strategy. Recovery = successful briefing / all trials in sparse, flood, noisy, and apifail scenarios. Judge tokens are excluded from strategy token totals."""
    from collections import defaultdict
    groups = defaultdict(list)
    with open(src, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                groups[row["strategy"]].append(row)
    for line in open("results_corrected.jsonl", encoding="utf-8"):
        row = json.loads(line)
        if row["scenario"] == "apifail":
            groups[row["strategy"]].append(row)

    summary = {}
    def mean(values):
        values = [v for v in values if isinstance(v, (int, float))]
        return round(sum(values) / len(values), 4) if values else None

    for strategy, rows in groups.items():
        successful = [r for r in rows if r.get("ok")]
        injected_scenarios = {"sparse", "flood", "noisy", "apifail"}
        injected = [r for r in rows if r.get("scenario") in injected_scenarios]
        judged = [r.get("judge") or {} for r in rows]
        summary[strategy] = {
            "trials": len(rows),
            "mean_end_to_end_latency_s": mean([r.get("latency_s") for r in rows]),
            "mean_llm_calls": mean([r.get("llm_calls") for r in rows]),
            "mean_estimated_cost_per_successful_briefing_usd": mean([r.get("cost_per_successful_briefing_usd") for r in successful]),
            "mean_faithfulness_1_to_5": mean([j.get("faithfulness") for j in judged]),
            "mean_coverage_1_to_5": mean([j.get("coverage") for j in judged]),
            "task_completion_rate_pct": round(100 * len(successful) / len(rows), 2) if rows else None,
            "injected_failure_recovery_rate_pct": round(100 * sum(bool(r.get("ok")) for r in injected) / len(injected), 2) if injected else None,
            "mean_input_tokens": mean([r.get("input_tokens") for r in rows]),
            "mean_output_tokens": mean([r.get("output_tokens") for r in rows]),
            "mean_total_tokens": mean([r.get("total_tokens") for r in rows]),
            "injected_trials": len(injected),
            "recovery_definition": "successful briefing / all sparse, flood, noisy, and apifail trials",
            "judge_scored_trials": sum(1 for j in judged if j.get("faithfulness") is not None),
        }
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2))
    return summary


# ── Email ─────────────────────────────────────────────────────────────────────
def send_email(to: str, subject: str, body: str):
    resend.api_key = os.environ.get("RESEND_API_KEY")
    if not resend.api_key:
        print("Resend API key not set")
        return
    try:
        r = resend.Emails.send({
            "from":    "News Agent <onboarding@resend.dev>",
            "to":      to,
            "subject": subject,
            "text":    body,
        })
        print(f"Email sent: {r}")
    except Exception as e:
        print(f"Email error: {e}")


def run_job(topics: List[str], email: Optional[str]):
    briefing = RUNNERS[STRATEGY](topics)
    if email:
        send_email(email, f"Daily Briefing: {', '.join(topics)}", briefing)


def parse_message(msg: str, prev_email: Optional[str]) -> dict:
    resp = llm.invoke([
        SystemMessage(content=(
            "Extract from the user message and return ONLY valid JSON with keys:\n"
            '- "topics": list of news topics (strings)\n'
            '- "email": email address or null\n'
            '- "schedule": "now" | "in_minutes" | "at_time" | "daily"\n'
            '- "value": minutes as int if in_minutes, "HH:MM" string if at_time or daily, null if now\n'
            'Use "daily" if user says "every day", "daily", "each day", "every morning/evening" etc.'
        )),
        HumanMessage(content=msg)
    ])
    try:
        raw    = re.sub(r"```json|```", "", resp.content).strip()
        parsed = json.loads(raw)
        parsed["email"] = parsed.get("email") or prev_email
        return parsed
    except:
        return {"topics": ["technology"], "email": prev_email, "schedule": "now", "value": None}


# ── Gradio chat ───────────────────────────────────────────────────────────────
def chat(message: str, history: list) -> str:
    prev_email = None
    for h in history:
        raw = h.get("content", "") if isinstance(h, dict) else h
        if isinstance(raw, list):
            content = " ".join(i.get("text", "") if isinstance(i, dict) else str(i) for i in raw)
        else:
            content = str(raw)
        m = re.search(r"[\w.+\-]+@[\w.\-]+\.\w{2,}", content)
        if m:
            prev_email = m.group(0)
            break

    p        = parse_message(message, prev_email)
    topics   = p.get("topics") or ["technology"]
    email    = p.get("email")
    schedule = p.get("schedule", "now")
    value    = p.get("value")

    email_note = f"\n📬 Will be sent to **{email}**." if email else \
                 "\n💡 Add your email and I'll send it there too."

    if schedule == "now":
        briefing = RUNNERS[STRATEGY](topics)
        if email:
            send_email(email, f"Briefing: {', '.join(topics)}", briefing)
        return (f"📰 **Briefing: {', '.join(topics)}** _(strategy: {STRATEGY})_{email_note}\n\n---\n\n{briefing}")

    elif schedule == "in_minutes":
        mins     = int(value) if value else 5
        run_time = datetime.now(IST) + timedelta(minutes=mins)
        scheduler.add_job(run_job, "date", run_date=run_time, args=[topics, email])
        return (f"✅ Scheduled! **{', '.join(topics)}** briefing in **{mins} min** "
                f"({run_time.strftime('%I:%M %p')} IST).{email_note}")

    elif schedule == "at_time":
        from dateutil import parser as dp
        t        = dp.parse(str(value)) if value else datetime.now(IST).replace(hour=9, minute=0)
        now      = datetime.now(IST)
        run_time = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
        if run_time <= now:
            run_time += timedelta(days=1)
        scheduler.add_job(run_job, "date", run_date=run_time, args=[topics, email])
        return (f"✅ Scheduled! **{', '.join(topics)}** briefing at "
                f"**{run_time.strftime('%I:%M %p')} IST**.{email_note}")

    elif schedule == "daily":
        from dateutil import parser as dp
        t      = dp.parse(str(value)) if value else datetime.now(IST).replace(hour=9, minute=0)
        job_id = f"daily_{email}_{','.join(topics)}"
        scheduler.add_job(
            run_job, "cron",
            hour=t.hour, minute=t.minute,
            timezone=IST,
            args=[topics, email],
            id=job_id,
            replace_existing=True
        )
        return (f"✅ Daily briefing set! You'll get **{', '.join(topics)}** news "
                f"every day at **{t.strftime('%I:%M %p')} IST**.{email_note}\n\n"
                f"💡 To cancel say: *'cancel my daily {', '.join(topics)} briefing'*")

    return "Try: *'Send me AI news now'* or *'cybersecurity news every day at 8 AM to me@gmail.com'*"


if __name__ == "__main__":
    if os.environ.get("EXPERIMENT"):          # EXPERIMENT=1 python news_agent_coordination_metrics_fixed.py   (runs all 3 strategies, resumable)
        experiment([["AI"], ["cybersecurity"], ["India tech startups"]],
                   n=int(os.environ.get("N_TRIALS", "10")),
                   out=os.environ.get("EXPERIMENT_OUT", "results_v3.jsonl"),
                   scenarios=tuple(os.environ.get("SCENARIOS", "normal,sparse,flood,noisy,transient").split(",")),
                   strategies=tuple(os.environ.get("STRATS", "linear,dynamic_graph,critic_only,routing_only").split(",")))
    elif os.environ.get("SCORE"):             # SCORE=1 runs the LLM judge pass
        score_results(
            src=os.environ.get("SCORE_SRC", "results.jsonl"),
            dst=os.environ.get("SCORE_DST", "scored.jsonl"),
        )
    elif os.environ.get("SUMMARIZE"):         # SUMMARIZE=1 aggregates metrics
        summarize_results(
            src=os.environ.get("SUMMARY_SRC", "scored.jsonl"),
            dst=os.environ.get("SUMMARY_DST", "summary.json"),
        )
    else:
        gr.ChatInterface(
            fn=chat,
            title="📰 Autonomous News Briefing Agent",
            description="Tell me what news you want, when, and optionally your email.",
            examples=[
                "Send me AI news right now to harshkaushikdev@gmail.com",
                "Cybersecurity news in 5 minutes to harshkaushikdev@gmail.com",
                "Send me AI news every day at 8 AM to harshkaushikdev@gmail.com",
                "India Tech and startup news daily at 9 PM to harshkaushikdev@gmail.com",
            ],
        ).launch(
            server_name="0.0.0.0",
            server_port=int(os.environ.get("PORT", 7860)),
            show_error=True,
        )