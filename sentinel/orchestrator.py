"""The Orchestrator (LangGraph): understand each event, send it to the right agent, then send the alerts.

    START -> router -> phishing / incident / cost / voc -> alert -> END

The router is an LLM: it reads ANY event, even a free-text message like "the website is slow and people can't log in",
and decides which specialist agent should handle it (and why). Offline, it uses keywords.
"""
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from . import config
from .cost_agent import analyze_costs
from .incident_agent import analyze_incident
from .llm import get_llm
from .phishing_agent import analyze_email
from .reporter import alert_email, send_email
from .voc_agent import analyze_reviews

NEEDS_ALERT = ["phishing", "suspicious", "critical", "warning"]
EVENT_TYPES = {"email": "phishing", "incident": "incident", "cost": "cost", "feedback": "voc"}
KEYWORDS = {   # offline router: words that point to each agent
    "phishing": ["email", "e-mail", "mail", "link", "password", "sender", "phishing", "attachment", "ايميل", "رسالة", "لينك"],
    "incident": ["server", "ssh", "login", "log in", "error", "down", "slow", "outage", "hack", "سيرفر", "الموقع", "واقع"],
    "cost": ["cost", "bill", "budget", "token", "spend", "price", "money", "invoice", "تكلفة", "فلوس", "ميزانية", "فاتورة"],
    "voc": ["customer", "review", "complain", "feedback", "rating", "عملاء", "عميل", "شكوى", "تقييم", "مراجعات"],
}

ROUTER_PROMPT = """You are the Orchestrator of Sentinel, an AI operations team. Send this event to ONE specialist:
- phishing: a suspicious email, a link, a request for a password or money by email
- incident: servers, logins, attacks on servers, errors, the website is down or slow
- cost: AI / cloud spending, bills, budget, tokens, model prices
- voc: customers, reviews, complaints, feedback, ratings
Event:
{event}"""


class State(TypedDict, total=False):
    event_type: str    # email, incident, cost or feedback (optional)
    text: str          # or: a free-text event, e.g. a message from an employee
    data: dict         # the event's data (for an email: raw_email, reported_by)
    agent: str         # chosen by the router
    route_reason: str  # why the router chose it
    result: dict       # the agent's answer
    messages: list     # what the alert step sent


class Route(BaseModel):
    agent: Literal["phishing", "incident", "cost", "voc"]
    reason: str = Field(description="One short sentence: why this agent")


# ---------- 1. Router: which agent? ----------
def keyword_route(text):
    text = text.lower()
    hits = {agent: sum(word in text for word in words) for agent, words in KEYWORDS.items()}
    best = max(hits, key=hits.get)
    return (best, f"keywords: {best}") if hits[best] else ("incident", "no keyword matched: incident by default")


def route_event(state, llm=None):
    data = dict(state.get("data") or {})
    if state.get("event_type") in EVENT_TYPES:                       # a known event type: no need to ask
        agent, reason = EVENT_TYPES[state["event_type"]], f"event type '{state['event_type']}'"
    else:
        text = state.get("text", "")
        agent, reason = keyword_route(text)
        llm = llm or get_llm()
        if llm:
            try:
                route = llm.with_structured_output(Route).invoke(ROUTER_PROMPT.format(event=text[:3000]))
                agent, reason = route.agent, f"LLM router: {route.reason}"
            except Exception as error:
                reason += f" (LLM not used: {type(error).__name__})"
        if agent == "phishing" and "raw_email" not in data:           # a pasted email becomes the email to analyse
            data["raw_email"] = text if text.lstrip().lower().startswith(("from:", "subject:")) else f"Subject: Reported message\n\n{text}"
    return {"agent": agent, "route_reason": reason, "data": data}


def router(state):
    """The router node of the graph."""
    return route_event(state)


def pick_agent(state):
    return state["agent"]


# ---------- 2. The agents ----------
def phishing_node(state):
    return {"result": analyze_email(state["data"]["raw_email"])}


def incident_node(state):
    return {"result": analyze_incident(state["data"].get("ssh"), state["data"].get("web"))}


def cost_node(state):
    return {"result": analyze_costs(state["data"].get("usage"), state["data"].get("model"))}


def voc_node(state):
    return {"result": analyze_reviews(state["data"].get("reviews"))}


# ---------- 3. Alerts ----------
def alert_node(state):
    result = state["result"]
    messages = []

    employee = state["data"].get("reported_by")
    if employee:   # the LLM wrote a reply for the employee (or we use the summary)
        reply = result["extra"].get("reply_to_employee") or result["summary"]
        messages.append(send_email(employee, f"Your report: {result['verdict']}", f"<p>{reply}</p>"))

    if result["verdict"] in NEEDS_ALERT:
        team = {"Phishing Triage": config.SECURITY_TEAM_EMAIL, "Incident Commander": config.ONCALL_EMAIL,
                "Cost Watchdog": config.CTO_EMAIL, "Arabic VoC": config.PRODUCT_EMAIL}[result["agent"]]
        subject, html = alert_email(result)
        messages.append(send_email(team, subject, html))

    return {"messages": messages}


# ---------- 4. Build the graph ----------
def build_graph():
    graph = StateGraph(State)
    graph.add_node("router", router)
    graph.add_node("phishing", phishing_node)
    graph.add_node("incident", incident_node)
    graph.add_node("cost", cost_node)
    graph.add_node("voc", voc_node)
    graph.add_node("alert", alert_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", pick_agent, ["phishing", "incident", "cost", "voc"])
    for agent in ["phishing", "incident", "cost", "voc"]:
        graph.add_edge(agent, "alert")
    graph.add_edge("alert", END)
    return graph.compile()


def handle_event(event_type=None, data=None, text=None):
    """Main entry point: give Sentinel an event (a type + data, or just free text) and get back the final state."""
    return build_graph().invoke({"event_type": event_type or "", "text": text or "", "data": data or {}})
