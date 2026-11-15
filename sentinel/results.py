"""Every agent returns its answer in the SAME shape, so one reporter can handle all agents."""
from datetime import datetime

from pydantic import BaseModel, Field

# Guardrail for actions: anything that changes a system or touches customers waits for a human
RISKY_WORDS = ["block", "disable", "turn off", "turn on", "delete", "remove", "reset", "roll back", "rollback", "restart",
               "shut", "disconnect", "change", "move", "switch", "limit", "contact", "refund", "migrate"]


class Action(BaseModel):
    """One next step proposed by an LLM agent."""
    action: str = Field(description="One concrete next step")
    risky: bool = Field(description="True if it changes a system or affects people: a human must approve it")


def needs_approval(action):
    """True if a human must approve. Risky words always need a human, even if the LLM said 'not risky'."""
    return action.risky or any(word in action.action.lower() for word in RISKY_WORDS)


def make_result(agent, title, verdict, score, findings, summary, actions, steps=None, decided_by="rules (offline)",
                extra=None):
    return {
        "agent": agent,            # which agent answered
        "title": title,            # short title
        "verdict": verdict,        # phishing / suspicious / safe, or critical / warning / ok
        "score": score,            # evidence points from the rule checks (the guardrail)
        "findings": findings,      # list of {"reason", "points"}
        "summary": summary,        # explanation for humans (written by the LLM when there is one)
        "actions": actions,        # list of {"action", "needs_approval"}
        "steps": steps or [],      # the agent's thinking: [{"tool", "input", "result"}]
        "decided_by": decided_by,  # "LLM agent", "LLM agent + guardrail" or "rules (offline)"
        "extra": extra or {},      # anything else (e.g. the reply to the employee, the LLM's own verdict)
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
