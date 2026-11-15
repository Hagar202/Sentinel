"""The Incident Commander (an LLM agent with tools): read real server logs -> find attacks and errors -> decide
how serious it is -> write the plan and the status update for the on-call engineer.

Data: real logs from Loghub (an SSH server under attack, and an Apache web server).
The LLM investigates with tools and follows the incident runbook (RAG). Guardrails: an attacker who logged in is
always critical, and every risky action (block, reset, roll back...) waits for a human approval.
"""
import re
from typing import Literal

import pandas as pd
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from . import config, memory
from .knowledge import find_policy
from .llm import get_llm, run_agent
from .results import Action, make_result, needs_approval

SSH_LOG = config.ROOT / "datasets" / "logs" / "OpenSSH_2k.log"
WEB_LOG = config.ROOT / "datasets" / "logs" / "Apache_2k.log"
IP = r"(\d+\.\d+\.\d+\.\d+)"


# ---------- 1. Read the logs into tables ----------
def read_ssh_log(path=SSH_LOG):
    """One row per interesting SSH event: time, event, user, ip."""
    rows = []
    for line in open(path, encoding="utf-8", errors="replace"):
        time = line[:15]                                   # "Dec 10 06:55:46"
        if m := re.search(r"Failed password for (?:invalid user )?(\S+) from " + IP, line):
            rows.append({"time": time, "event": "failed login", "user": m.group(1), "ip": m.group(2)})
        elif m := re.search(r"Invalid user (\S+) from " + IP, line):
            rows.append({"time": time, "event": "unknown user", "user": m.group(1), "ip": m.group(2)})
        elif m := re.search(r"Accepted password for (\S+) from " + IP, line):
            rows.append({"time": time, "event": "successful login", "user": m.group(1), "ip": m.group(2)})
        elif m := re.search(r"\[" + IP + r"\] failed - POSSIBLE BREAK-IN ATTEMPT", line):
            rows.append({"time": time, "event": "break-in warning", "user": "", "ip": m.group(1)})
    table = pd.DataFrame(rows)
    table["minute"] = table["time"].str[:12]                  # "Dec 10 06:55"
    return table


def read_web_log(path=WEB_LOG):
    """One row per Apache log line: time, level (error / notice / ...), message."""
    rows = []
    for line in open(path, encoding="utf-8", errors="replace"):
        if m := re.match(r"\[(\w+ \w+ \d+ [\d:]+) \d+\] \[(\w+)\] (.*)", line):
            rows.append({"time": m.group(1), "level": m.group(2), "message": m.group(3).strip()})
    table = pd.DataFrame(rows)
    table["minute"] = table["time"].str[:16]                  # "Sun Dec 04 04:47"
    return table


def decide(score):
    if score >= 5:
        return "critical"
    if score >= 2:
        return "warning"
    return "ok"


SYSTEM_PROMPT = """You are Sentinel's Incident Commander, the on-call SRE / security engineer.
Investigate the server logs with your tools, follow the company incident runbook (search it), then decide the severity
(critical, warning or ok), write a short status update for the team, and list the next actions.
Only use numbers that your tools returned. Mark an action as risky if it changes a system or affects users."""


class IncidentReport(BaseModel):
    severity: Literal["critical", "warning", "ok"]
    summary: str = Field(description="3 short sentences: what is happening and what to do first")
    status_update: str = Field(description="A short message for the team channel")
    actions: list[Action]


# ---------- 2. The rule checks (the guardrail, and the offline answer) ----------
def rule_checks(ssh, web):
    findings = []
    failed = ssh[ssh["event"] == "failed login"]
    per_ip = failed["ip"].value_counts()
    attackers = per_ip[per_ip >= 20]
    if len(attackers):
        findings.append({"reason": f"Brute-force attack: {len(attackers)} IPs failed to log in 20+ times "
                                   f"(worst: {attackers.index[0]}, {attackers.iloc[0]} tries)", "points": 3})

    logins = ssh[ssh["event"] == "successful login"]
    broke_in = logins[logins["ip"].isin(attackers.index)]
    if len(broke_in):
        findings.append({"reason": f"An attacking IP logged in successfully: {broke_in['ip'].iloc[0]} "
                                   f"as '{broke_in['user'].iloc[0]}'", "points": 5})

    unknown_users = ssh[ssh["event"] == "unknown user"]["user"]
    if unknown_users.nunique() >= 10:
        examples = ", ".join(unknown_users.value_counts().index[:3])
        findings.append({"reason": f"Attackers guessed {unknown_users.nunique()} different usernames (most tried: {examples})",
                         "points": 2})

    errors = web[web["level"] == "error"]
    error_share = len(errors) / max(len(web), 1) * 100
    if error_share >= 20:
        top_error = re.sub(r"\d+", "N", errors["message"].value_counts().index[0])
        findings.append({"reason": f"Web server: {error_share:.0f}% of log lines are errors (most common: '{top_error[:70]}')",
                         "points": 2})

    per_minute = errors["minute"].value_counts()
    if len(per_minute) and per_minute.iloc[0] >= 3 * max(per_minute.median(), 1):
        findings.append({"reason": f"Error spike at {per_minute.index[0]}: {per_minute.iloc[0]} errors in one minute "
                                   f"(normal: {per_minute.median():.0f})", "points": 1})
    return findings, failed, attackers, broke_in, error_share


# ---------- 3. The tools (the agent decides which ones to call) ----------
def make_tools(ssh, web):
    failed = ssh[ssh["event"] == "failed login"]
    errors = web[web["level"] == "error"]

    @tool
    def failed_logins(top_n: int = 5) -> str:
        """Failed SSH logins: total, how many different IPs, and the IPs that failed the most."""
        top = failed["ip"].value_counts().head(top_n)
        return (f"{len(failed)} failed logins from {failed['ip'].nunique()} IPs. Top: "
                + ", ".join(f"{ip} ({n})" for ip, n in top.items()))

    @tool
    def attacker_logins(min_failures: int = 20) -> str:
        """Did any IP that failed many times then log in successfully? (= the attacker got in)"""
        per_ip = failed["ip"].value_counts()
        attackers = per_ip[per_ip >= min_failures].index
        logins = ssh[ssh["event"] == "successful login"]
        inside = logins[logins["ip"].isin(attackers)]
        if len(inside):
            return "ATTACKER LOGGED IN: " + ", ".join(f"{r.ip} as {r.user} at {r.time}" for r in inside.itertuples())
        return (f"No attacking IP ({len(attackers)} IPs with {min_failures}+ failures) logged in. "
                f"Successful logins in the log: {len(logins)} (" + ", ".join(f"{r.user} from {r.ip}" for r in logins.itertuples()) + ")")

    @tool
    def guessed_usernames(top_n: int = 5) -> str:
        """Usernames that do not exist but attackers tried (a sign of a scripted attack)."""
        users = ssh[ssh["event"] == "unknown user"]["user"]
        return f"{users.nunique()} different unknown usernames. Most tried: " + ", ".join(
            f"{u} ({n})" for u, n in users.value_counts().head(top_n).items())

    @tool
    def web_errors(top_n: int = 3) -> str:
        """Web server (Apache) errors: error rate and the most common error messages."""
        messages = errors["message"].str.replace(r"\d+", "N", regex=True).value_counts().head(top_n)
        return (f"{len(errors)} errors in {len(web)} log lines ({len(errors) / max(len(web), 1):.0%}). Most common: "
                + "; ".join(f"'{m[:80]}' ({n})" for m, n in messages.items()))

    @tool
    def error_spikes(top_n: int = 3) -> str:
        """The minutes with the most web errors, compared with a normal minute."""
        per_minute = errors["minute"].value_counts()
        return f"Normal minute: {per_minute.median():.0f} errors. Worst minutes: " + ", ".join(
            f"{m} ({n})" for m, n in per_minute.head(top_n).items())

    @tool
    def search_runbook(question: str) -> str:
        """Search the company incident runbook (RAG): severity levels and what to do for each kind of incident."""
        return find_policy(question) or "No matching runbook section."

    return [failed_logins, attacker_logins, guessed_usernames, web_errors, error_spikes, search_runbook]


# ---------- 4. The agent ----------
def analyze_incident(ssh=None, web=None, llm=None, use_llm=True, remember=True):
    ssh = ssh if ssh is not None else read_ssh_log()
    web = web if web is not None else read_web_log()

    # A. Rule checks: the guardrail, and the answer when there is no LLM
    findings, failed, attackers, broke_in, error_share = rule_checks(ssh, web)
    score = sum(f["points"] for f in findings)
    verdict, steps, decided_by, extra = decide(score), [], "rules (offline)", {"rules_verdict": decide(score)}
    summary = (f"{len(failed)} failed SSH logins from {failed['ip'].nunique()} IPs; "
               f"{len(attackers)} look like brute-force attackers. Web server error rate {error_share:.0f}%.")
    actions = [{"action": "Page the on-call engineer", "needs_approval": False}]
    if len(attackers):
        actions.append({"action": f"Block the top {min(len(attackers), 5)} attacking IPs on the firewall "
                                  f"({', '.join(attackers.index[:5])})", "needs_approval": True})
        actions.append({"action": "Turn off password login for SSH (keys only)", "needs_approval": True})
    if len(broke_in):
        actions.append({"action": f"Reset the password of '{broke_in['user'].iloc[0]}' and check that server",
                        "needs_approval": True})

    # B. The LLM agent investigates, follows the runbook and writes the plan
    llm = llm or (get_llm() if use_llm else None)
    if llm:
        try:
            task = ("Investigate the SSH log (2,000 lines) and the Apache web server log (2,000 lines) of our servers. "
                    "How serious is it, and what should the on-call engineer do?")
            report, steps = run_agent(llm, SYSTEM_PROMPT, task, make_tools(ssh, web), IncidentReport)
            verdict, summary, decided_by = report.severity, report.summary, "LLM agent"
            extra.update(llm_verdict=report.severity, status_update=report.status_update)
            actions = [{"action": "Page the on-call engineer", "needs_approval": False}] if verdict != "ok" else []
            actions += [{"action": a.action, "needs_approval": needs_approval(a)} for a in report.actions[:5]]
            # C. Guardrail: an attacker inside is ALWAYS critical
            if len(broke_in) and verdict != "critical":
                verdict, decided_by = "critical", "LLM agent + guardrail"
                summary += " [Guardrail: an attacking IP logged in successfully, so this is critical.]"
        except Exception as error:          # wrong key, no internet, free limit reached -> keep the rule-based answer
            summary += f" (LLM not used: {type(error).__name__}: {str(error)[:160]})"

    result = make_result("Incident Commander", "SSH + web server logs", verdict, score, findings, summary, actions,
                         steps, decided_by, extra)
    if remember:
        memory.save(result)
    return result
