"""Run all four Sentinel agents on the real data, through the Orchestrator.   Usage:  python main.py"""
from pathlib import Path

from sentinel import config
from sentinel.orchestrator import handle_event
from sentinel.reporter import daily_brief, send_email


def show(state):
    result = state["result"]
    print(f"\n=== {result['agent']}: {result['title']} ===")
    print(f"Verdict: {result['verdict'].upper()}   (decided by: {result['decided_by']}, rule points {result['score']})")
    for n, step in enumerate(result["steps"], 1):                     # how the LLM agent investigated
        print(f"   {n}. {step['tool']}({step['input']}) -> {step['result'][:100]}")
    if not result["steps"]:
        for finding in result["findings"]:
            print(f"   {finding['points']:+d}  {finding['reason']}")
    print("Summary:", result["summary"])
    print("Sent:", state["messages"])


# 1. Phishing: every sample email
for path in sorted(Path("samples").glob("*.eml")):
    show(handle_event("email", {"raw_email": path.read_bytes(), "reported_by": "employee@sentinel-demo.com"}))

# 2. The other three agents (they read the real logs, AI traffic and reviews)
show(handle_event("incident"))
show(handle_event("cost"))
show(handle_event("feedback"))

# 3. The daily brief for management
subject, html = daily_brief()
print("\nDaily brief:", subject, "->", send_email(config.SECURITY_TEAM_EMAIL, subject, html))
