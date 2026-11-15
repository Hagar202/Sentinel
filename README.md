# Sentinel: AI Operations Command Center

> A multi-agent Generative AI system that watches a company's security, servers, AI spending and customers, built on real public data.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-1C3C3C)
![Gemini](https://img.shields.io/badge/LLM-Gemini%20%7C%20Groq%20%7C%20OpenAI-4285F4?logo=googlegemini&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-REST%20API-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-TypeScript-61DAFB?logo=react&logoColor=black)
![Tests](https://github.com/Hagar202/Sentinel/actions/workflows/tests.yml/badge.svg)

Digital Hub (D-Hub) final project, by **Hagar Soliman**.

![Sentinel command center](docs/screenshots/overview.jpg)

## What it does

A **LangGraph orchestrator** reads every event, even a free-text message such as *"the website is slow and people
can't log in"*, and an **LLM router** sends it to one of four specialist **LLM agents**. Each agent chooses which
**tools** to call, reads the results, searches company policies with **RAG**, and returns a **structured answer**:
verdict, explanation, reply to the user and next actions. **Guardrails** keep it safe, and risky actions always wait
for a human to approve them.

| Agent | Job | Real data |
| --- | --- | --- |
| 📧 **Phishing Triage** | Investigates reported emails | 200 real phishing emails (Phishing Pot) + 500 real normal emails (Enron) |
| 🚨 **Incident Commander** | Finds attacks and error storms in server logs | Real SSH + Apache logs (Loghub) |
| 💰 **Cost Watchdog** | Prices AI traffic and finds savings | 28,000 real LLM requests (Azure trace) × current model prices (LiteLLM) |
| 💬 **Arabic Voice of Customer** | Finds what customers complain about | 4,272 real Arabic product reviews (souq.com) |

## Architecture

```mermaid
flowchart TB
    UI["React web app<br/>Vite + TypeScript + Tailwind"] --> API["FastAPI<br/>REST API + /docs"]
    API --> R{"LangGraph orchestrator<br/>LLM router (keywords when offline)"}

    subgraph AG["Specialist LLM agents (tool calling)"]
        direction LR
        P["📧 Phishing Triage"]
        I["🚨 Incident Commander"]
        C["💰 Cost Watchdog"]
        V["💬 Arabic VoC"]
    end

    R --> AG
    AG <-.->|"RAG: Gemini embeddings + FAISS"| K[("Company policies<br/>security · runbook · AI cost")]
    AG <-.->|memory| M[("SQLite<br/>results · history · decisions")]
    AG --> G["Guardrails<br/>rule checks + ML model"]
    G --> A["Alert step"]
    A --> E["Alert emails + daily brief"]
    A --> H["Human approval for risky actions"]
```

### How one agent works

Each agent runs the same loop (`sentinel/llm.py`): the LLM decides which tool to call, reads the result, and repeats
until it can answer. The tools do the facts and the maths; the LLM never computes numbers itself.

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant A as LLM agent
    participant T as Tools
    participant K as Policies (RAG)
    participant G as Guardrail
    O->>A: event (e.g. a reported email)
    loop up to AGENT_MAX_STEPS
        A->>T: call a tool (check_link, inspect_sender, ask_ml_model ...)
        T-->>A: evidence
        A->>K: search_policy("what to do with ...")
        K-->>A: matching policy text
    end
    A->>G: structured answer (Pydantic): verdict, summary, reply, actions
    G-->>O: final verdict (the guardrail can only make it stricter)
```

### Key design decisions

1. **One job per agent.** Each agent has its own tools, prompt and tests, so it can be improved alone.
2. **Explainable verdicts.** Every phishing verdict comes with reasons and points a human can check.
3. **The LLM can't be tricked into "safe".** The email is treated as data, prompt-injection attempts add points, and
   the rule checks run on every email: a high score or an injection can never end as "safe".
4. **Numbers come from code, not from the LLM.** Calculator and log tools compute everything; the LLM explains.
5. **Humans approve risky actions.** Blocking a domain or deleting emails needs a click on the Approvals page.
6. **Works with any LLM, or none.** Gemini with automatic fallback (Gemini Lite, then Groq), or OpenAI. With
   `LLM_PROVIDER=offline` the whole system still runs on the rule checks and the ML model.

## Results on real data

**Rules + ML model (the guardrail), all 700 labelled emails:**

| Measure | Result |
| --- | --- |
| Phishing detected | **90%** (200 real phishing emails) |
| Normal emails wrongly flagged | **0.6%** (500 real normal emails) |
| Precision | **98.4%** |
| Accuracy | **96.7%** |
| Speed | ~5 ms per email (no LLM) |

**Rules vs LLM agent vs LLM agent + guardrail** (same 10 phishing + 10 normal emails, Gemini):

| Method | Detection | False alarms | Accuracy | Time per email |
| --- | --- | --- | --- | --- |
| Rules + ML | 80% | 0% | 90% | ~9 ms |
| LLM agent | 90% | 0% | 95% | ~16 s |
| LLM agent + guardrail | 90% | 0% | 95% | ~16 s |

The LLM agent catches more phishing, but it is ~2,000× slower. That is why the fast rules run on every email and the
LLM investigates. The LLM sample is small because of the free API rate limit; the full run is in the notebook
(section 11) and on the **Evaluation** page.

**Arabic sentiment** with a word-list baseline: 68% on 4,272 reviews (3 classes).

## Screenshots

| Phishing Triage | Incident Commander |
| --- | --- |
| ![Phishing](docs/screenshots/phishing.jpg) | ![Incidents](docs/screenshots/incident.jpg) |
| **Cost Watchdog** | **Arabic Voice of Customer** |
| ![Costs](docs/screenshots/costs.jpg) | ![Arabic VoC](docs/screenshots/voc.jpg) |
| **Evaluation** | |
| ![Evaluation](docs/screenshots/evaluation.jpg) | |

The web app has 9 pages: Overview, Approvals, Phishing, Incidents, Costs, Arabic VoC, Evaluation, Reports and System.

## Tech stack

| Layer | Tools |
| --- | --- |
| Agents & orchestration | LangGraph, LangChain, tool calling, Pydantic structured outputs |
| LLMs | Gemini (default, with fallbacks), Groq, OpenAI, or offline |
| RAG | Gemini embeddings + FAISS over company policy documents |
| ML | scikit-learn phishing model, pandas, NumPy |
| Backend | FastAPI, SQLite, SMTP alerts (dry-run by default) |
| Frontend | React, TypeScript, Vite, Tailwind, Recharts |
| Quality | pytest (38 tests with a fake LLM, no API key needed), GitHub Actions |

## Run it

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env

pytest -q                          # 38 tests, no API key needed
python main.py                     # runs all four agents in the terminal
uvicorn api.main:app --reload      # the web app
```

Open **http://localhost:8000** for the app and **http://localhost:8000/docs** for the API.
The React app is already built (`frontend/dist`), so Node.js is not needed to run it.

**Turn on the LLM agents:** add a free Gemini key in `.env` (`LLM_PROVIDER=gemini`, `GOOGLE_API_KEY=...`).
A `GROQ_API_KEY` is used as a backup when Gemini is busy. Without a key, keep `LLM_PROVIDER=offline`.

**Change the design:**

```bash
cd frontend
npm install
npm run dev        # live preview on http://localhost:5173 (keep uvicorn running)
npm run build      # rebuild frontend/dist
```

## API

All endpoints are documented at `/docs`. The main ones:

| Endpoint | What it does |
| --- | --- |
| `POST /api/ask` | Free-text event → LLM router → agent → answer |
| `POST /api/run-all` | Runs all four agents on real data |
| `POST /api/phishing/analyze` · `POST /api/phishing/upload` | Analyse a demo or uploaded `.eml` email |
| `POST /api/incident/run` · `POST /api/costs/run` · `POST /api/voc/run` | Run one agent |
| `GET /api/approvals` · `POST /api/approvals` | List and approve / reject risky actions |
| `GET /api/evaluation` · `POST /api/evaluation/llm` | Evaluation results; run the LLM comparison |
| `GET /api/reports/brief` | Daily brief |

## Project structure

```
sentinel/
  orchestrator.py    LangGraph: LLM router -> agent -> alert
  llm.py             LLM choice + fallbacks + run_agent(): the tool-calling loop
  knowledge.py       RAG: policy documents -> Gemini embeddings -> FAISS
  results.py         the shape every agent returns + the action guardrail
  phishing_agent.py  investigates an email with tools, decides, replies
  incident_agent.py  real logs + runbook -> severity, plan, status update
  cost_agent.py      real LLM traffic x prices (calculator tools) -> savings
  voc_agent.py       reads real Arabic reviews -> complaint topics
  checks.py          phishing rule checks (each gives points)
  email_reader.py    email -> simple dictionary
  memory.py          SQLite: results, "seen before?", human decisions
  evaluation.py      rules vs LLM agent vs LLM agent + guardrail
  reporter.py        alert emails, daily brief
  config.py          settings from .env
api/main.py          FastAPI REST API (+ serves the React app)
frontend/            React app (src/pages = one file per page, dist = built app)
knowledge/           policies for RAG: security policy, incident runbook, AI cost policy, model prices
datasets/            real data, with sources and licenses (datasets/README.md)
models/              trained phishing ML model
notebooks/           the whole project step by step in one notebook
samples/             3 hand-made demo emails
tests/               pytest
docs/                project story, demo script, deployment, screenshots
```

## Limits and next steps

- The LLM comparison uses a small sample (20 emails) because of the free API rate limit.
- The Arabic sentiment baseline is a word list (68%); a fine-tuned Arabic model would do better.
- Next: deploy a live demo, add tracing for agent steps, and run the LLM evaluation on the full dataset.

## Data and credits

All datasets are public; sources, licenses and citations are in [`datasets/README.md`](datasets/README.md).
More detail on the idea and design: [`docs/PROJECT_STORY.md`](docs/PROJECT_STORY.md).

---

**Hagar Soliman** · [LinkedIn](https://www.linkedin.com/in/hagar-soliman-ai) · [GitHub](https://github.com/Hagar202) · [Portfolio](https://hagar202.github.io/portfolio/)
