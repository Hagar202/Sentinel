"""Tests for the FastAPI backend: every page of the web app talks to these endpoints."""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from sentinel import config

client = TestClient(app)


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    """Use a temporary database and outbox, so tests don't touch the real ones."""
    monkeypatch.setattr(config, "LLM_PROVIDER", "offline")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "OUTBOX_DIR", tmp_path / "outbox")
    monkeypatch.setattr(config, "DRY_RUN", True)


def test_health():
    data = client.get("/api/health").json()
    assert data["dry_run"] is True  # tests must never send real emails


def test_analyze_demo_email():
    result = client.post("/api/phishing/analyze", json={"source": "demo", "name": "ceo_fraud_injection.eml"}).json()
    assert result["verdict"] == "phishing"


def test_path_traversal_is_blocked():
    response = client.get("/api/phishing/preview", params={"source": "demo", "name": "../../.env"})
    assert response.status_code == 404


def test_incident_and_costs_stats():
    assert client.get("/api/incident/stats").json()["failed_logins"] > 0
    assert client.get("/api/costs/stats", params={"model": "gpt-4o", "budget": 60000}).json()["requests"] > 0


def test_voc_reviews_filter():
    data = client.get("/api/voc/reviews", params={"topic": "All", "sentiment": "negative"}).json()
    assert data["total"] > 0


def test_ask_routes_free_text_to_an_agent():
    answer = client.post("/api/ask", json={"text": "our AI bill is way over the budget"}).json()
    assert answer["agent"] == "cost" and answer["result"]["agent"] == "Cost Watchdog"
    assert client.post("/api/ask", json={"text": "  "}).status_code == 400


def test_health_says_how_the_agents_run():
    assert client.get("/api/health").json()["agents_mode"] == "rules only (offline)"
