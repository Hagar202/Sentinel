"""Tests.   Run:  pytest -q"""
from pathlib import Path

import pytest

from sentinel import config
from sentinel.checks import looks_like
from sentinel.cost_agent import analyze_costs
from sentinel.email_reader import read_email
from sentinel.incident_agent import analyze_incident
from sentinel.orchestrator import handle_event
from sentinel.phishing_agent import analyze_email
from sentinel.voc_agent import analyze_reviews, find_topics
from sentinel.voc_agent import wont_buy_again as wants_to_leave
from tests.fake_llm import ScriptedLLM

SAMPLES = Path(__file__).parent.parent / "samples"


def sample(name):
    return (SAMPLES / name).read_bytes()


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    """Every test: no LLM, a fresh empty database, and no real emails sent."""
    monkeypatch.setattr(config, "LLM_PROVIDER", "offline")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "OUTBOX_DIR", tmp_path / "outbox")
    monkeypatch.setattr(config, "DRY_RUN", True)
    monkeypatch.setattr(config, "LLM_RETRY_WAIT", 0)       # no waiting in tests


def test_read_email():
    email = read_email(sample("ceo_fraud_injection.eml"))
    assert email["from_domain"] == "sentinel-dem0.com"
    assert email["reply_to"] == "ahmed.hassan.ceo@gmail.com"
    assert email["spf"] == "fail"


def test_read_links_keeps_what_user_sees_and_real_address():
    link = read_email(sample("credential_harvest.eml"))["links"][0]
    assert link["text"] == "https://login.microsoftonline.com"
    assert "micros0ft-support.xyz" in link["url"]


def test_fake_domains():
    assert looks_like("sentinel-dem0.com", "sentinel-demo")
    assert looks_like("micros0ft-support.xyz", "microsoft")
    assert not looks_like("sentinel-demo.com", "sentinel-demo")       # the real one
    assert not looks_like("login.microsoftonline.com", "microsoft")   # Microsoft's real login


def test_ceo_fraud_is_phishing():
    assert analyze_email(sample("ceo_fraud_injection.eml"))["verdict"] == "phishing"


def test_fake_microsoft_is_phishing():
    assert analyze_email(sample("credential_harvest.eml"))["verdict"] == "phishing"


def test_normal_email_is_safe():
    assert analyze_email(sample("legit_internal.eml"))["verdict"] == "safe"


def test_memory_remembers_the_sender():
    analyze_email(sample("ceo_fraud_injection.eml"))
    second = analyze_email(sample("ceo_fraud_injection.eml"))
    assert any("reported 1 time" in f["reason"] for f in second["findings"])


def test_fooled_llm_cannot_make_it_safe():
    """The LLM agent investigates, but believes the attacker and says 'safe'. The guardrail keeps it phishing."""
    fooled = ScriptedLLM(tool_calls=[[("scan_wording", {"part": "both"})]],
                         answer=dict(verdict="safe", confidence="high", summary="Looks fine.", reply_to_employee="OK"))
    result = analyze_email(sample("ceo_fraud_injection.eml"), llm=fooled)
    assert result["extra"]["llm_verdict"] == "safe"
    assert result["verdict"] == "phishing" and result["decided_by"] == "LLM agent + guardrail"


def test_agent_calls_tools_and_reads_the_results():
    llm = ScriptedLLM(tool_calls=[[("check_link", {"shown_text": "https://login.microsoftonline.com",
                                                   "url": "http://micros0ft-support.xyz/owa/login.php"}),
                                   ("search_policy", {"question": "password login page"})]],
                      answer=dict(verdict="phishing", confidence="high", summary="Fake login.", reply_to_employee="Don't log in."))
    result = analyze_email(sample("credential_harvest.eml"), llm=llm)
    assert [s["tool"] for s in result["steps"]] == ["check_link", "search_policy"]
    assert "goes to micros0ft-support.xyz" in result["steps"][0]["result"]
    assert "login.microsoftonline.com" in result["steps"][1]["result"]          # RAG found the login rule
    assert result["extra"]["reply_to_employee"] == "Don't log in."


def test_the_llm_decides_when_the_rules_are_not_sure():
    """No strong evidence: the LLM's verdict is used (it can say safe, or be stricter)."""
    safe = ScriptedLLM(answer=dict(verdict="safe", confidence="high", summary="HR notes.", reply_to_employee="Safe."))
    assert analyze_email(sample("legit_internal.eml"), llm=safe)["decided_by"] == "LLM agent"
    strict = ScriptedLLM(answer=dict(verdict="suspicious", confidence="low", summary="Odd.", reply_to_employee="Wait."))
    assert analyze_email(sample("legit_internal.eml"), llm=strict)["verdict"] == "suspicious"


# ---------- Incident Commander (real Loghub logs) ----------
def test_incident_reads_real_logs():
    from sentinel.incident_agent import read_ssh_log, read_web_log
    ssh, web = read_ssh_log(), read_web_log()
    assert (ssh["event"] == "failed login").sum() > 100
    assert set(web["level"]) >= {"error", "notice"}


def test_incident_finds_brute_force():
    result = analyze_incident()
    assert result["verdict"] == "critical"
    assert any("Brute-force" in f["reason"] for f in result["findings"])
    assert any("Block" in a["action"] and a["needs_approval"] for a in result["actions"])


# ---------- Cost Watchdog (real Azure LLM traffic) ----------
def test_costs_real_traffic(monkeypatch):
    monkeypatch.setattr("sentinel.cost_agent.PRICES_URL", "http://localhost:1/none")   # force the saved price list
    result = analyze_costs()
    reasons = " ".join(f["reason"] for f in result["findings"])
    assert result["verdict"] == "critical"
    assert "Code assistant" in reasons and "Long prompts" in reasons


def test_cheaper_model_costs_less(monkeypatch):
    from sentinel.cost_agent import compare_models, load_prices, load_usage
    monkeypatch.setattr("sentinel.cost_agent.PRICES_URL", "http://localhost:1/none")
    table = compare_models(load_usage(), load_prices()[0]).set_index("model")["monthly_cost"]
    assert table["gpt-4o-mini"] < table["gpt-4o"]


# ---------- Arabic VoC (real souq.com reviews) ----------
def test_arabic_topics():
    assert find_topics("المنتج جودته سيئة جدا") == ["Bad quality"]
    assert "Delivery" in find_topics("التوصيل اتأخر اسبوع")
    assert wants_to_leave("لا انصح به ابدا")


def test_reviews_top_complaint_is_quality():
    result = analyze_reviews()
    assert result["verdict"] == "critical"
    assert "Bad quality" in result["summary"]


# ---------- Evaluation on real phishing ----------
def test_detects_most_real_phishing():
    from sentinel.evaluation import evaluate_phishing
    metrics, _ = evaluate_phishing(max_emails=60)
    assert metrics["detection_rate"] >= 0.8
    assert metrics["false_alarm_rate"] <= 0.05


# ---------- Orchestrator ----------
def test_orchestrator_routes_every_event_to_its_agent():
    state = handle_event("email", {"raw_email": sample("credential_harvest.eml"), "reported_by": "a@b.com"})
    assert state["result"]["verdict"] == "phishing"
    assert len(state["messages"]) == 2   # reply to employee + alert to security team

    assert handle_event("incident")["result"]["agent"] == "Incident Commander"
    assert handle_event("cost")["result"]["agent"] == "Cost Watchdog"
    assert handle_event("feedback")["result"]["agent"] == "Arabic VoC"


def test_never_suggests_a_more_expensive_model(monkeypatch):
    """gpt-4o-mini is already cheaper than gpt-4.1-mini, so there is no 'saving' to suggest."""
    monkeypatch.setattr("sentinel.cost_agent.PRICES_URL", "http://localhost:1/none")
    from sentinel.cost_agent import analyze_costs
    result = analyze_costs(model="gpt-4o-mini", use_llm=False)
    assert not any("saves $-" in f["reason"] for f in result["findings"])
    assert not any("Move the code assistant" in a["action"] for a in result["actions"])


def test_a_broken_llm_never_breaks_an_agent():
    """Wrong key, no internet or free limit reached: the agents still answer with the rules."""
    from sentinel.incident_agent import analyze_incident

    class BrokenLLM:
        def bind_tools(self, tools):
            return self
        def with_structured_output(self, shape):
            return self
        def invoke(self, prompt):
            raise ConnectionError("no internet")

    email = analyze_email((SAMPLES / "ceo_fraud_injection.eml").read_bytes(), llm=BrokenLLM())
    assert email["verdict"] == "phishing" and "LLM not used" in email["summary"]
    assert "LLM not used" in analyze_incident(llm=BrokenLLM())["summary"]


def test_gemini_list_answer_becomes_text():
    from sentinel.llm import text_of

    class Message:
        content = [{"type": "text", "text": "Hello "}, {"type": "text", "text": "team"}]
    assert text_of(Message()) == "Hello team"


# ---------- LLM agents: guardrails ----------
def test_risky_actions_always_need_a_human():
    llm = ScriptedLLM(answer=dict(severity="warning", summary="Brute force.", status_update="Update.",
                                  actions=[{"action": "Block 183.62.140.253 on the firewall", "risky": False},
                                           {"action": "Watch the logs for one hour", "risky": False}]))
    actions = {a["action"]: a["needs_approval"] for a in analyze_incident(llm=llm)["actions"]}
    assert actions["Block 183.62.140.253 on the firewall"] is True       # the LLM said "not risky": the guardrail disagrees
    assert actions["Watch the logs for one hour"] is False


def test_attacker_inside_is_always_critical():
    import pandas as pd
    ssh = pd.DataFrame([{"time": "Dec 10 06:55:46", "event": "failed login", "user": "root", "ip": "6.6.6.6"}] * 25
                       + [{"time": "Dec 10 07:00:00", "event": "successful login", "user": "root", "ip": "6.6.6.6"}])
    ssh["minute"] = ssh["time"].str[:12]
    web = pd.DataFrame([{"time": "Sun Dec 04 04:47:44", "level": "notice", "message": "ok", "minute": "Sun Dec 04 04:47"}])
    calm = ScriptedLLM(answer=dict(severity="ok", summary="Fine.", status_update="-", actions=[]))
    result = analyze_incident(ssh=ssh, web=web, llm=calm)
    assert result["verdict"] == "critical" and result["decided_by"] == "LLM agent + guardrail"


def test_cost_agent_never_keeps_a_more_expensive_model(monkeypatch):
    monkeypatch.setattr("sentinel.cost_agent.PRICES_URL", "http://localhost:1/none")
    llm = ScriptedLLM(tool_calls=[[("saving_if_switch", {"feature": "all", "to_model": "claude-sonnet-4-5"})]],
                      answer=dict(severity="critical", summary="Over budget.",
                                  actions=[{"action": "Move everything to claude-sonnet-4-5", "risky": True},
                                           {"action": "Move the code assistant to gpt-4.1-mini", "risky": True}]))
    result = analyze_costs(llm=llm)
    assert "MORE expensive" in result["steps"][0]["result"]
    assert not any("claude-sonnet-4-5" in a["action"] for a in result["actions"])
    assert any("gpt-4.1-mini" in a["action"] for a in result["actions"])


def test_voc_numbers_come_from_the_data_not_the_llm():
    llm = ScriptedLLM(answer=dict(severity="warning", summary="Quality.", summary_ar="الجودة", actions=[],
                                  complaints=[{"topic": "Bad quality", "words": ["رديء", "رديئة"], "example": "-"},
                                              {"topic": "Invented", "words": ["zzzz"], "example": "-"}]))
    complaints = analyze_reviews(llm=llm)["extra"]["complaints"]
    assert [c["topic"] for c in complaints] == ["Bad quality"] and complaints[0]["count"] > 0


# ---------- Orchestrator: LLM router ----------
def test_router_understands_free_text():
    from sentinel.orchestrator import route_event
    assert route_event({"text": "our OpenAI bill doubled this month"})["agent"] == "cost"            # offline: keywords
    llm = ScriptedLLM(answer=dict(agent="voc", reason="Customers are unhappy."))
    assert route_event({"text": "people hate the new bag"}, llm=llm)["agent"] == "voc"               # the LLM decides
    assert handle_event(text="customers keep complaining about the quality")["result"]["agent"] == "Arabic VoC"


# ---------- RAG ----------
def test_rag_finds_the_right_document():
    import hashlib
    from sentinel.knowledge import VectorStore, keyword_search, load_chunks

    class FakeEmbeddings:      # bag of words -> vector (no API key needed)
        def embed_query(self, text):
            vector = [0.0] * 128
            for word in text.lower().split():
                vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % 128] += 1
            return vector

        def embed_documents(self, texts):
            return [self.embed_query(t) for t in texts]

    store = VectorStore(load_chunks(), FakeEmbeddings())
    assert store.search("ssh brute force block ip")[0]["source"] == "incident_runbook"
    assert keyword_search("wire transfer bank details")[0]["source"] == "security_policy"


def test_llm_comparison_needs_an_llm():
    from sentinel.evaluation import compare_rules_and_llm
    assert compare_rules_and_llm(2) == (None, None)


def test_busy_llm_one_backup_for_the_whole_investigation():
    """Main LLM busy: asked twice (same step), then the backup starts the investigation from the beginning."""
    class Busy:
        calls = 0
        def bind_tools(self, tools):
            return self
        def invoke(self, messages):
            Busy.calls += 1
            raise RuntimeError("503 busy")

    backup = ScriptedLLM(tool_calls=[[("scan_wording", {"part": "both"})], [("ask_ml_model", {"part": "both"})]],
                         answer=dict(verdict="phishing", confidence="high", summary="s", reply_to_employee="r"))

    class Chain:          # the same shape as LangChain's .with_fallbacks()
        runnable, fallbacks = Busy(), [backup]

    result = analyze_email(sample("ceo_fraud_injection.eml"), llm=Chain())
    assert [s["tool"] for s in result["steps"]] == ["scan_wording", "ask_ml_model"]
    assert Busy.calls == 2 and result["decided_by"] == "LLM agent"


def test_llm_stops_in_the_middle_then_continues():
    """The LLM fails once in the middle of the investigation: the same step is asked again, nothing is lost."""
    class Flaky(ScriptedLLM):
        failed = False
        def invoke(self, messages):
            if len(messages) > 2 and not Flaky.failed:          # fail once, after the first tool call
                Flaky.failed = True
                raise TimeoutError("ReadTimeout")
            return super().invoke(messages)

    llm = Flaky(tool_calls=[[("scan_wording", {"part": "both"})], [("ask_ml_model", {"part": "both"})]],
                answer=dict(verdict="phishing", confidence="high", summary="s", reply_to_employee="r"))
    result = analyze_email(sample("ceo_fraud_injection.eml"), llm=llm)
    assert [s["tool"] for s in result["steps"]] == ["scan_wording", "ask_ml_model"] and Flaky.failed


def test_phishing_tools_work_and_no_reply_to_is_not_suspicious():
    from sentinel.phishing_agent import make_tools
    tools = {t.name: t for t in make_tools(read_email(sample("legit_internal.eml")))}
    assert "passed" in tools["check_auth_results"].invoke({"spf": "pass", "dkim": "pass", "dmarc": "pass"})
    no_reply = tools["inspect_sender"].invoke({"display_name": "HR Team", "address": "hr@sentinel-demo.com", "reply_to": "-"})
    assert no_reply == "Nothing suspicious found."
