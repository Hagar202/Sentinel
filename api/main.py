"""Sentinel REST API (FastAPI).   Run:  uvicorn api.main:app --reload

- Every page of the web app talks to Sentinel only through these endpoints.
- Open http://localhost:8000/docs to try every endpoint in the browser.
- The built React app (frontend/dist) is served at http://localhost:8000
"""
from functools import lru_cache
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sentinel import config, memory
from sentinel.cost_agent import compare_models, cost_of, load_prices, load_usage
from sentinel.email_reader import read_email
from sentinel.evaluation import PHISHING_DIR, compare_rules_and_llm, evaluate_phishing, evaluate_sentiment
from sentinel.incident_agent import read_ssh_log, read_web_log
from sentinel.llm import get_llm
from sentinel.orchestrator import build_graph, handle_event
from sentinel.phishing_agent import analyze_email
from sentinel.reporter import daily_brief, send_email
from sentinel.voc_agent import TOPICS, find_topics, load_reviews, wont_buy_again

app = FastAPI(title="Sentinel API", description="AI Operations Command Center: 4 agents behind one API.",
              version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DEMO_DIR = config.ROOT / "samples"
AGENTS = ["Phishing Triage", "Incident Commander", "Cost Watchdog", "Arabic VoC"]
REPORTER = "employee@sentinel-demo.com"


# ---------- Loaders (read the real data once, then keep it in memory) ----------
@lru_cache
def ssh_log():
    return read_ssh_log()


@lru_cache
def web_log():
    return read_web_log()


@lru_cache
def usage():
    return load_usage()


@lru_cache
def reviews():
    table = load_reviews()
    table["topics"] = table["text"].apply(find_topics)
    table["dont_recommend"] = table["text"].apply(wont_buy_again)
    return table


@lru_cache
def phishing_evaluation():
    metrics, table = evaluate_phishing()
    return {k: float(v) for k, v in metrics.items()}, table


@lru_cache
def sentiment_evaluation():
    return evaluate_sentiment()


def email_path(source, name):
    folder = DEMO_DIR if source == "demo" else PHISHING_DIR
    path = folder / Path(name).name          # .name stops "../" tricks
    if not path.exists():
        raise HTTPException(404, f"No email called {name}")
    return path


# ---------- System ----------
@app.get("/api/health")
def health():
    llm_ready = get_llm() is not None
    return {"llm_provider": config.LLM_PROVIDER, "llm_connected": llm_ready, "dry_run": config.DRY_RUN,
            "agents_mode": "LLM agents + guardrails" if llm_ready else "rules only (offline)",
            "llm_model": config.GEMINI_MODEL if config.LLM_PROVIDER == "gemini" else config.LLM_PROVIDER,
            "company_domain": config.COMPANY_DOMAIN, "current_model": config.CURRENT_MODEL,
            "monthly_budget": config.AI_MONTHLY_BUDGET}


@app.get("/api/system/graph")
def graph():
    return {"mermaid": build_graph().get_graph().draw_mermaid()}


# ---------- Overview ----------
@app.get("/api/overview")
def overview():
    results = memory.all_results()
    latest = {}
    for result in results:
        latest.setdefault(result["agent"], result)
    counts = pd.DataFrame(results).groupby(["agent", "verdict"]).size().reset_index(name="events") if results else []
    return {
        "total": len(results),
        "urgent": sum(r["verdict"] in ["phishing", "critical"] for r in results),
        "waiting": len(approvals()),
        "agents_online": len(latest),
        "latest": [latest.get(agent) for agent in AGENTS],
        "counts": counts.to_dict("records") if len(counts) else [],
        "feed": results[:25],
    }


@app.post("/api/run-all")
def run_all():
    """Send one event of every type through the Orchestrator, on real data."""
    emails = sorted(PHISHING_DIR.glob("*.eml"))[:2] + sorted(DEMO_DIR.glob("*.eml"))   # few emails: the free LLM has a rate limit
    for path in emails:
        handle_event("email", {"raw_email": path.read_bytes(), "reported_by": REPORTER})
    for event in ["incident", "cost", "feedback"]:
        handle_event(event)
    return overview()


class AskRequest(BaseModel):
    text: str                     # any event in plain words, or a pasted email
    reported_by: str = REPORTER


@app.post("/api/ask")
def ask(request: AskRequest):
    """Tell Sentinel what happened in plain words: the LLM router picks the agent, the agent investigates."""
    if not request.text.strip():
        raise HTTPException(400, "Write what happened")
    state = handle_event(text=request.text, data={"reported_by": request.reported_by})
    return {"agent": state["agent"], "route_reason": state["route_reason"], "result": state["result"],
            "messages": state.get("messages", [])}


# ---------- Phishing ----------
@app.get("/api/phishing/emails")
def list_emails():
    demo = [p.name for p in sorted(DEMO_DIR.glob("*.eml"))]
    real = [p.name for p in sorted(PHISHING_DIR.glob("*.eml"), key=lambda p: int(p.stem.split("-")[1]))]
    return {"demo": demo, "real": real}


@app.get("/api/phishing/preview")
def preview(source: str, name: str):
    email = read_email(email_path(source, name).read_bytes())
    email["body"] = email["body"][:1500]
    return email


class AnalyzeRequest(BaseModel):
    source: str = "demo"      # demo | real
    name: str


@app.post("/api/phishing/analyze")
def analyze(request: AnalyzeRequest):
    raw = email_path(request.source, request.name).read_bytes()
    return handle_event("email", {"raw_email": raw, "reported_by": REPORTER})["result"]


@app.post("/api/phishing/upload")
async def upload(file: UploadFile = File(...)):
    raw = await file.read()
    return handle_event("email", {"raw_email": raw, "reported_by": REPORTER})["result"]


@app.get("/api/phishing/scan")
def scan(count: int = 100):
    rows = []
    for path in sorted(PHISHING_DIR.glob("*.eml"))[:count]:
        result = analyze_email(path.read_bytes(), use_llm=False, remember=False)
        top = max(result["findings"], key=lambda f: f["points"])["reason"] if result["findings"] else "-"
        rows.append({"email": path.name, "subject": result["title"][:80], "verdict": result["verdict"],
                     "score": result["score"], "reason": top})
    caught = sum(r["verdict"] != "safe" for r in rows)
    return {"rows": rows, "caught": caught / max(len(rows), 1)}


# ---------- Incident ----------
@app.get("/api/incident/stats")
def incident_stats():
    ssh, web = ssh_log(), web_log()
    failed = ssh[ssh["event"] == "failed login"]
    per_ip = failed["ip"].value_counts()
    per_minute = ssh.pivot_table(index="minute", columns="event", values="ip", aggfunc="count", fill_value=0)
    errors = web[web["level"] == "error"].groupby("minute", sort=False).size()   # keep the log order (sorting the text would put "Mon" before "Sun")
    return {
        "failed_logins": len(failed),
        "attacking_ips": int((per_ip >= 20).sum()),
        "usernames_guessed": int(ssh[ssh["event"] == "unknown user"]["user"].nunique()),
        "web_error_rate": float((web["level"] == "error").mean()),
        "per_minute": per_minute.reset_index().to_dict("records"),
        "events": list(per_minute.columns),
        "top_ips": [{"ip": ip, "count": int(n)} for ip, n in per_ip.head(10).items()],
        "web_errors": [{"minute": m, "errors": int(n)} for m, n in errors.items()],
        "recent": ssh[ssh["event"].isin(["failed login", "successful login"])].tail(30).to_dict("records"),
    }


@app.post("/api/incident/run")
def incident_run():
    return handle_event("incident")["result"]


# ---------- Costs ----------
@app.get("/api/costs/stats")
def cost_stats(model: str = config.CURRENT_MODEL, budget: float = config.AI_MONTHLY_BUDGET):
    data, (prices, source) = usage(), load_prices()
    if model not in set(prices["model"]):
        raise HTTPException(400, f"Unknown model {model}")
    comparison = compare_models(data, prices)
    monthly = float(comparison.set_index("model").loc[model, "monthly_cost"])
    per_minute = data.set_index("time").groupby("feature").resample("1min").size().unstack(0, fill_value=0)
    by_feature = data.assign(cost=cost_of(data, model, prices)).groupby("feature")["cost"].sum()
    bins = pd.cut(data["input_tokens"], [0, 500, 1000, 2000, 4000, 8000, 16000])
    return {
        "requests": len(data), "monthly_cost": monthly, "budget": budget, "budget_used": monthly / budget,
        "cheapest": comparison.iloc[0].to_dict(), "price_source": source, "models": list(prices["model"]),
        "comparison": comparison.to_dict("records"),
        "per_minute": [{"time": t.strftime("%H:%M"), **{k: int(v) for k, v in row.items()}}
                       for t, row in per_minute.iterrows()],
        "by_feature": [{"feature": f, "cost": float(c)} for f, c in by_feature.items()],
        "prompt_sizes": [{"range": str(b), "requests": int(n)} for b, n in bins.value_counts(sort=False).items()],
    }


class CostRequest(BaseModel):
    model: str = config.CURRENT_MODEL
    budget: float = config.AI_MONTHLY_BUDGET


@app.post("/api/costs/run")
def cost_run(request: CostRequest):
    config.AI_MONTHLY_BUDGET = request.budget
    return handle_event("cost", {"model": request.model})["result"]


# ---------- Arabic Voice of the Customer ----------
@app.get("/api/voc/stats")
def voc_stats():
    table = reviews()
    unhappy = table[table["sentiment"] == "negative"]
    topics = unhappy["topics"].explode().value_counts()
    return {
        "reviews": len(table), "negative_share": len(unhappy) / len(table),
        "dont_recommend": int(table["dont_recommend"].sum()),
        "top_topic": topics.index[0], "top_topic_count": int(topics.iloc[0]),
        "sentiment": [{"sentiment": s, "count": int(n)} for s, n in table["sentiment"].value_counts().items()],
        "topics": [{"topic": t, "count": int(n)} for t, n in topics.items()],
        "topic_names": list(TOPICS),
    }


@app.get("/api/voc/reviews")
def voc_reviews(topic: str = "All", sentiment: str = "negative", limit: int = 20):
    table = reviews()
    if sentiment != "All":
        table = table[table["sentiment"] == sentiment]
    if topic != "All":
        table = table[table["topics"].apply(lambda t: topic in t)]
    return {"total": len(table), "rows": table[["text", "sentiment", "topics"]].head(limit).to_dict("records")}


@app.post("/api/voc/run")
def voc_run():
    return handle_event("feedback")["result"]


# ---------- Approvals (human in the loop) ----------
@app.get("/api/approvals")
def approvals():
    decided = {(d["agent"], d["action"]) for d in memory.decisions()}
    latest = {}
    for result in memory.all_results():
        latest.setdefault(result["agent"], result)
    return [{"agent": r["agent"], "verdict": r["verdict"], "title": r["title"], "action": a["action"]}
            for r in latest.values() for a in r["actions"]
            if a["needs_approval"] and (r["agent"], a["action"]) not in decided]


class Decision(BaseModel):
    agent: str
    action: str
    decision: str     # approved | rejected


@app.post("/api/approvals")
def decide(decision: Decision):
    if decision.decision not in ["approved", "rejected"]:
        raise HTTPException(400, "decision must be 'approved' or 'rejected'")
    memory.save_decision(decision.agent, decision.action, decision.decision)
    return {"ok": True}


@app.get("/api/decisions")
def decisions():
    return memory.decisions()


# ---------- Evaluation ----------
@app.get("/api/evaluation")
def evaluation():
    metrics, table = phishing_evaluation()
    sentiment, confusion = sentiment_evaluation()
    by_label = table.groupby(["truth", "verdict"]).size().unstack(fill_value=0)
    scores = table.groupby(["truth", "score"]).size().unstack(0, fill_value=0)
    return {
        "phishing": metrics,
        "by_label": [{"truth": t, **{k: int(v) for k, v in row.items()}} for t, row in by_label.iterrows()],
        "scores": [{"score": int(s), **{k: int(v) for k, v in row.items()}} for s, row in scores.iterrows()],
        "sentiment": {"reviews": int(sentiment["reviews"]), "accuracy": float(sentiment["accuracy"])},
        "confusion": {"labels": list(confusion.columns),
                      "rows": [{"truth": t, **{k: int(v) for k, v in row.items()}} for t, row in confusion.iterrows()]},
        "llm_comparison": llm_comparison(),
    }


def llm_comparison():
    """The saved result of the rules vs LLM experiment (made by the notebook or the button), if there is one."""
    path = config.DB_PATH.parent / "llm_comparison.csv"
    return pd.read_csv(path).to_dict("records") if path.exists() else None


class CompareRequest(BaseModel):
    emails_each: int = 5          # real phishing + the same number of real normal emails


@app.post("/api/evaluation/llm")
def run_llm_comparison(request: CompareRequest):
    """Rules vs LLM agent vs LLM agent + guardrail on a sample of real emails (slow: the free LLM has a rate limit)."""
    comparison, _ = compare_rules_and_llm(max(1, min(request.emails_each, 25)))
    if comparison is None:
        raise HTTPException(400, "No LLM: add an API key in .env")
    return llm_comparison()


# ---------- Reports ----------
BRIEF_CACHE = {}


@app.get("/api/reports/brief")
def brief():
    """The LLM writes the brief once per new result (not on every page visit)."""
    key = len(memory.todays_results())
    if key not in BRIEF_CACHE:
        BRIEF_CACHE.clear()
        BRIEF_CACHE[key] = daily_brief()
    subject, html = BRIEF_CACHE[key]
    return {"subject": subject, "html": html}


@app.post("/api/reports/send")
def send_brief():
    subject, html = daily_brief()
    return {"status": send_email(config.SECURITY_TEAM_EMAIL, subject, html)}


@app.get("/api/results")
def results():
    return memory.all_results()


@app.get("/api/outbox")
def outbox():
    files = sorted(config.OUTBOX_DIR.glob("*.html"), reverse=True)[:30] if config.OUTBOX_DIR.exists() else []
    return [{"name": p.name, "html": p.read_text(encoding="utf-8")} for p in files]


# ---------- The web app (built React files) ----------
DIST = config.ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def web_app(path: str):
        file = DIST / path
        return FileResponse(file if path and file.is_file() else DIST / "index.html")
