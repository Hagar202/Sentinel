"""The Cost Watchdog (an LLM agent with tools): real LLM traffic x real prices -> monthly cost, waste and savings.

Data: one hour of real LLM requests from Azure production (chat + code services), and the LiteLLM price list.
The LLM investigates with calculator tools (it never does the maths itself) and follows the AI cost policy (RAG).
Guardrails: over 100% of the budget is always critical, it can never suggest a MORE expensive model,
and every change waits for a human approval.
"""
import re
from typing import Literal

import pandas as pd
import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from . import config, memory
from .knowledge import find_policy
from .llm import get_llm, run_agent
from .results import Action, make_result, needs_approval

TRACES = {"chatbot": config.ROOT / "datasets" / "azure_llm_trace_conv.csv",
          "code_assistant": config.ROOT / "datasets" / "azure_llm_trace_code.csv"}
PRICES_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
LITELLM_NAMES = {"gpt-4o": "gpt-4o", "gpt-4o-mini": "gpt-4o-mini", "gpt-4.1": "gpt-4.1", "gpt-4.1-mini": "gpt-4.1-mini",
                 "gpt-4.1-nano": "gpt-4.1-nano", "gemini-2.5-pro": "gemini/gemini-2.5-pro",
                 "gemini-2.5-flash": "gemini/gemini-2.5-flash", "claude-sonnet-4-5": "claude-sonnet-4-5",
                 "claude-haiku-4-5": "claude-haiku-4-5"}
HOURS_PER_MONTH = 24 * 30


# ---------- 1. Get the data ----------
def load_usage():
    """Every real request: time, which service, input tokens, output tokens."""
    tables = []
    for feature, path in TRACES.items():
        table = pd.read_csv(path, parse_dates=["TIMESTAMP"])
        table["feature"] = feature
        tables.append(table)
    usage = pd.concat(tables).rename(columns={"TIMESTAMP": "time", "ContextTokens": "input_tokens",
                                              "GeneratedTokens": "output_tokens"})
    return usage.sort_values("time").reset_index(drop=True)


def load_prices():
    """Today's prices from LiteLLM (dollars per 1M tokens). No internet -> the saved copy."""
    try:
        data = requests.get(PRICES_URL, timeout=5).json()
        rows = [{"model": name, "input_price": data[key]["input_cost_per_token"] * 1e6,
                 "output_price": data[key]["output_cost_per_token"] * 1e6} for name, key in LITELLM_NAMES.items()]
        return pd.DataFrame(rows), "live (LiteLLM)"
    except Exception:
        return pd.read_csv(config.KNOWLEDGE_DIR / "model_prices.csv"), "saved copy"


def cost_of(usage, model, prices):
    """Dollar cost of every request if it ran on `model`."""
    price = prices.set_index("model").loc[model]
    return (usage["input_tokens"] * price["input_price"] + usage["output_tokens"] * price["output_price"]) / 1_000_000


def compare_models(usage, prices):
    """Monthly cost of this traffic on every model in the price list."""
    hours = (usage["time"].max() - usage["time"].min()).total_seconds() / 3600
    rows = [{"model": m, "monthly_cost": cost_of(usage, m, prices).sum() / hours * HOURS_PER_MONTH}
            for m in prices["model"]]
    return pd.DataFrame(rows).sort_values("monthly_cost")


def decide(score):
    if score >= 5:
        return "critical"
    if score >= 2:
        return "warning"
    return "ok"


SYSTEM_PROMPT = """You are Sentinel's Cost Watchdog, a FinOps analyst for the company's AI spending.
Investigate with your tools (they do all the maths: never calculate yourself), follow the AI cost policy (search it),
then decide the severity (critical, warning or ok), explain it to the CTO, and list the actions with their saving.
Only suggest a cheaper model if saving_if_switch says it really saves money."""


class CostReport(BaseModel):
    severity: Literal["critical", "warning", "ok"]
    summary: str = Field(description="3 short sentences for the CTO: the cost, the biggest waste, what to do first")
    actions: list[Action]


# ---------- 2. The rule checks (the guardrail, and the offline answer) ----------
def rule_checks(usage, model, prices, hours):
    monthly = usage["cost"].sum() / hours * HOURS_PER_MONTH
    findings = []

    # Check 1: will we go over the monthly budget?
    percent = monthly / config.AI_MONTHLY_BUDGET * 100
    if percent > 80:
        findings.append({"reason": f"On {model}, this traffic costs about ${monthly:,.0f}/month: "
                                   f"{percent:.0f}% of the ${config.AI_MONTHLY_BUDGET:,.0f} budget",
                         "points": 3 if percent > 100 else 2})

    # Check 2: the code assistant writes very short answers -> a small model is enough
    code = usage[usage["feature"] == "code_assistant"]
    small_model_saving = 0
    if len(code) and code["output_tokens"].median() < 50 and model != config.CHEAP_MODEL:
        now = cost_of(code, model, prices).sum() / hours * HOURS_PER_MONTH
        cheap = cost_of(code, config.CHEAP_MODEL, prices).sum() / hours * HOURS_PER_MONTH
        small_model_saving = now - cheap
        if small_model_saving > 0:          # only suggest it if the other model is really cheaper
            findings.append({"reason": f"Code assistant answers are short (median {code['output_tokens'].median():.0f} tokens): "
                                       f"moving it to {config.CHEAP_MODEL} saves ${small_model_saving:,.0f}/month", "points": 2})

    # Check 3: a few long prompts cost a lot
    long = usage[usage["input_tokens"] > 4000]
    long_cost_share = long["cost"].sum() / usage["cost"].sum() * 100
    if long_cost_share >= 15:
        findings.append({"reason": f"Long prompts (>4,000 tokens) are {len(long) / len(usage) * 100:.0f}% of requests "
                                   f"but {long_cost_share:.0f}% of the cost: trim them or use prompt caching", "points": 2})

    # Check 4: traffic spikes
    per_minute = usage.set_index("time").resample("1min").size()
    if per_minute.max() >= 2 * per_minute.median():
        findings.append({"reason": f"Traffic spike: {per_minute.max()} requests in one minute "
                                   f"(normal: {per_minute.median():.0f})", "points": 1})
    return findings, monthly, percent, small_model_saving, long_cost_share


# ---------- 3. The tools (calculators the agent can call) ----------
def make_tools(usage, model, prices, hours):
    def monthly(rows, on_model):
        return cost_of(rows, on_model, prices).sum() / hours * HOURS_PER_MONTH

    def rows_of(feature):
        return usage if feature == "all" else usage[usage["feature"] == feature]

    @tool
    def monthly_cost(on_model: str) -> str:
        """Monthly cost of ALL our real traffic on one model, and how much of the monthly budget that is."""
        if on_model not in set(prices["model"]):
            return f"Unknown model. Known: {', '.join(prices['model'])}"
        cost = monthly(usage, on_model)
        return f"{on_model}: ${cost:,.0f}/month = {cost / config.AI_MONTHLY_BUDGET:.0%} of the ${config.AI_MONTHLY_BUDGET:,.0f} budget"

    @tool
    def compare_all_models(top_n: int = 9) -> str:
        """The same real traffic priced on every model in today's price list, cheapest first."""
        table = compare_models(usage, prices).head(top_n)
        return "; ".join(f"{r.model}: ${r.monthly_cost:,.0f}/month" for r in table.itertuples())

    @tool
    def feature_usage(feature: Literal["chatbot", "code_assistant", "all"]) -> str:
        """How a feature uses AI: requests, median input/output tokens, and its share of today's cost."""
        rows = rows_of(feature)
        return (f"{feature}: {len(rows):,} requests in {hours * 60:.0f} minutes, median input {rows['input_tokens'].median():.0f} "
                f"tokens, median output {rows['output_tokens'].median():.0f} tokens, "
                f"{rows['cost'].sum() / usage['cost'].sum():.0%} of the cost on {model}")

    @tool
    def saving_if_switch(feature: Literal["chatbot", "code_assistant", "all"], to_model: str) -> str:
        """Monthly saving if one feature moves from today's model to another model (negative = MORE expensive)."""
        if to_model not in set(prices["model"]):
            return f"Unknown model. Known: {', '.join(prices['model'])}"
        rows = rows_of(feature)
        saving = monthly(rows, model) - monthly(rows, to_model)
        verdict = "saves" if saving > 0 else "is MORE expensive by"
        return f"Moving {feature} from {model} to {to_model} {verdict} ${abs(saving):,.0f}/month"

    @tool
    def long_prompts(min_input_tokens: int = 4000) -> str:
        """How many requests have very long prompts, and how much of the cost they are."""
        long = usage[usage["input_tokens"] > min_input_tokens]
        return (f"{len(long):,} requests ({len(long) / len(usage):.0%}) have more than {min_input_tokens:,} input tokens "
                f"and cost {long['cost'].sum() / usage['cost'].sum():.0%} of the money")

    @tool
    def traffic_spikes(top_n: int = 3) -> str:
        """The busiest minutes compared with a normal minute."""
        per_minute = usage.set_index("time").resample("1min").size()
        return f"Normal minute: {per_minute.median():.0f} requests. Busiest: " + ", ".join(
            f"{t:%H:%M} ({n})" for t, n in per_minute.sort_values(ascending=False).head(top_n).items())

    @tool
    def search_cost_policy(question: str) -> str:
        """Search the company AI cost policy (RAG): budget rules, which model to use, who must approve changes."""
        return find_policy(question) or "No matching policy section."

    return [monthly_cost, compare_all_models, feature_usage, saving_if_switch, long_prompts, traffic_spikes,
            search_cost_policy]


def more_expensive(action, usage, model, prices):
    """Guardrail: does this action suggest a model that costs MORE than today's model?"""
    current = cost_of(usage, model, prices).sum()
    for other in prices["model"]:
        named = re.search(rf"(?<![\w.-]){re.escape(other.lower())}(?![\w.-])", action.lower())   # "gpt-4o" is not "gpt-4o-mini"
        if other != model and named and cost_of(usage, other, prices).sum() >= current:
            return True
    return False


# ---------- 4. The agent ----------
def analyze_costs(usage=None, model=None, llm=None, use_llm=True, remember=True):
    usage = usage if usage is not None else load_usage()
    model = model or config.CURRENT_MODEL
    prices, price_source = load_prices()
    usage = usage.assign(cost=cost_of(usage, model, prices))
    hours = (usage["time"].max() - usage["time"].min()).total_seconds() / 3600

    # A. Rule checks: the guardrail, and the answer when there is no LLM
    findings, monthly, percent, small_model_saving, long_cost_share = rule_checks(usage, model, prices, hours)
    score = sum(f["points"] for f in findings)
    verdict, steps, decided_by, extra = decide(score), [], "rules (offline)", {"rules_verdict": decide(score)}
    summary = (f"{len(usage):,} real requests in {hours * 60:.0f} minutes. On {model} that is about ${monthly:,.0f}/month. "
               f"Prices: {price_source}.")
    actions = [{"action": "Send the cost report to the CTO", "needs_approval": False}]
    if small_model_saving > 0:
        actions.append({"action": f"Move the code assistant to {config.CHEAP_MODEL}", "needs_approval": True})
    if long_cost_share >= 15:
        actions.append({"action": "Turn on prompt caching for long prompts", "needs_approval": True})
    if percent > 100:
        actions.append({"action": "Set a monthly spending limit on the API key", "needs_approval": True})

    # B. The LLM agent investigates with the calculators and writes the plan
    llm = llm or (get_llm() if use_llm else None)
    if llm:
        try:
            task = (f"The company runs its chatbot and code assistant on {model}. Monthly AI budget: "
                    f"${config.AI_MONTHLY_BUDGET:,.0f}. Prices: {price_source}. Are we wasting money, and how do we save?")
            report, steps = run_agent(llm, SYSTEM_PROMPT, task, make_tools(usage, model, prices, hours), CostReport)
            verdict, summary, decided_by = report.severity, report.summary, "LLM agent"
            extra["llm_verdict"] = report.severity
            actions = [{"action": "Send the cost report to the CTO", "needs_approval": False}]
            for a in report.actions[:5]:
                if more_expensive(a.action, usage, model, prices):         # C. Guardrail: never a pricier model
                    decided_by = "LLM agent + guardrail"
                    summary += f" [Guardrail: removed '{a.action}', that model is more expensive.]"
                    continue
                actions.append({"action": a.action, "needs_approval": True})   # every AI config change needs the CTO
            if percent > 100 and verdict != "critical":                         # C. Guardrail: over budget = critical
                verdict, decided_by = "critical", "LLM agent + guardrail"
                summary += f" [Guardrail: {percent:.0f}% of the budget is always critical.]"
        except Exception as error:          # wrong key, no internet, free limit reached -> keep the rule-based answer
            summary += f" (LLM not used: {type(error).__name__}: {str(error)[:160]})"

    result = make_result("Cost Watchdog", f"AI spend ≈ ${monthly:,.0f}/month", verdict, score, findings, summary, actions,
                         steps, decided_by, extra)
    if remember:
        memory.save(result)
    return result
