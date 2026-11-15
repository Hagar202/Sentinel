# Demo Video Script (about 8–10 minutes)

The Final Project brief asks for a **face-cam video** showing the system working **and** explaining the architecture and logic.
Plan: **Part 1 = the notebook** (how it works, on real data) · **Part 2 = the deployment** (the live web app).

## Before you record

- [ ] Run the whole notebook once (Kernel → Restart & Run All) with `LLM_PROVIDER=gemini`, so every output is fresh.
- [ ] Open the live Render link 1–2 minutes before recording (the free plan sleeps after 15 minutes).
- [ ] Recorder: **OBS**, **Loom** or **Windows Game Bar** (`Win + Alt + R`) with the webcam bubble on.
- [ ] Hide `.env`, API keys, WhatsApp and notifications. Zoom the notebook to 125% so the code is readable.

You can speak in English or Arabic. The lines below are a guide, not something to read word by word.

---

## Part 1 · The notebook

### 0:00 – 0:40 · Who you are and the problem (face + cell 0)

> "Hi, I'm Hagar Soliman. This is **Sentinel**, my final project for the AI Agents program by D-Hub and Orange Digital Center.
> A company faces four risks every day: phishing emails, attacks on its servers, wasted AI money, and unhappy customers.
> One AI can't watch them all, so Sentinel has **one specialist LLM agent per risk**, and an **Orchestrator** built with LangGraph
> that sends every event to the right agent. Everything runs on **real, public data**."

### 0:40 – 2:00 · The shared tools: what makes it an agent (sections 1–3)

1. Cell 5 output: `LLM: gemini`.
> "The generative model is **Google Gemini**, through LangChain, with a backup model if it's busy. No key? It still runs on rules + my ML model."
2. Section 3.3, `investigate()`: **the most important cell.**
> "This is the agent loop. The LLM gets the task and a list of tools. It decides which tool to call, we run it and give back the result,
> and it decides again, until it has enough evidence. Then it answers in a fixed shape: verdict, summary, reply, next actions."
3. Section 3.4, RAG output.
> "When the agent needs a company rule, it searches our policy documents: each section is embedded with Gemini embeddings and stored in FAISS.
> 'urgent wire transfer from the CEO' finds the Payments section of the security policy."
4. Section 3.1: the action guardrail.
> "Anything that blocks, deletes or contacts people waits for a human to approve."

### 2:00 – 3:45 · Agent 1: Phishing Triage (section 4)

1. Cell 16: the CEO email as a dictionary.
> "From 'Ahmed Hassan, CEO', but the domain is `sentinel-dem0` with a zero, replies go to Gmail, SPF and DMARC failed."
2. Section 4.2 table + cell 21: **+19, +22, −3 points.**
> "Each check gives points with a reason. One of the checks is my own ML model, TF-IDF + Logistic Regression."
3. Cell 26: the LLM agent's verdicts and the tools it chose.
4. **Cell 27: the key safety test.**
> "The attacker hid a sentence telling the AI to call this email safe. Here a fooled LLM says SAFE,
> but the guardrail sees 19 points of evidence and keeps it PHISHING. The LLM can make a verdict stricter, never weaker."

### 3:45 – 5:00 · Agents 2, 3, 4 (sections 5–7), about 25 seconds each

- **Incident (cell 35):** "Real SSH logs: 519 failed logins from 23 IPs, one IP tried 286 times: a brute-force attack.
  The LLM follows our runbook to set the severity. Blocking IPs waits for approval."
- **Cost (cells 42–43):** "28,000 real requests from Azure, priced with today's prices. On gpt-4o that's about $106,000 a month, 178% of the budget.
  The LLM never does the maths: its tools are calculators."
- **Arabic VoC (cell 51):** "4,272 real Arabic reviews. The LLM reads them itself, finds the complaint topics,
  then every topic is counted on all the reviews, so no number is made up."

### 5:00 – 6:00 · Orchestrator + demo (sections 8–10)

1. Cell 61: the LangGraph graph: `router → 4 agents → alert`.
2. **Cell 63: free text, even Egyptian Arabic, goes to the right agent.**
> "I don't tell Sentinel the event type. The LLM router reads 'العملاء بيشتكوا إن الخامة وحشة' and sends it to the Arabic VoC agent."
3. Cells 54 / 64: the alert email and the daily brief, written by the LLM.

### 6:00 – 7:00 · Evaluation (section 11)

> "Measured on **700 real labelled emails**, not my demo emails: the rules + ML catch **90%** of the attacks with **0.6%** false alarms,
> **96.7%** accuracy, in about 5 milliseconds per email.
> Then the key experiment: the same real emails three ways: rules, the LLM agent, and the LLM agent + guardrail.
> The LLM is much slower, seconds per email, so this runs on a sample. And the project has **38 automated tests**."

Mention one honest limit (section 12): "The LLM comparison is a small sample because of the free API's rate limit."

---

## Part 2 · The deployment

### 7:00 – 8:30 · Live web app

1. Show **GitHub**: the repo (and that `.env` is not there).
> "The same code is split into a package, a FastAPI REST API and a React web app, deployed for free on Render.
> The API key lives in Render's environment variables, never on GitHub, and `DRY_RUN` stops visitors from sending real emails."
2. Open the **live link → Overview** → type a free-text event in "Tell Sentinel what happened".
3. **Phishing Triage** → `ceo_fraud_injection.eml` → **Analyze email**.
4. **Approvals** → approve one action. "Every risky action from every agent lands here, and every decision is logged."
5. Open **`/docs`**. "Any app can use the agents through this API: web, mobile or a Slack bot."

### 8:30 – 9:00 · Closing (face)

> "Sentinel covers all six objectives: real data, LLM processing, automated alerts and reports, LangGraph orchestration,
> this presentation, and an evaluation on real data. Thank you!"

---

## If something goes wrong while recording

- The LLM is slow or busy → wait and re-run the cell; the backup model takes over. Last resort: `LLM_PROVIDER=offline`.
- The live app is slow at first → it was sleeping; wait a minute and refresh.
- The app shows old results → restart it (locally: stop uvicorn with `Ctrl + C`, delete the `data` folder, start again).
