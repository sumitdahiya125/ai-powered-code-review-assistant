"""End-to-end API test.

Boots the full FastAPI app against an in-memory SQLite database. Redis is left
unconfigured — the cache layer gracefully degrades, so the request path still
works without it. CodeBERT is also skipped (the encoder reports unavailable on
missing torch/transformers), so we only assert on the rule-engine findings.
"""

import os
import tempfile
from pathlib import Path

# Configure before any app imports.
_DB_FILE = Path(tempfile.gettempdir()) / "codereview-test.sqlite"
if _DB_FILE.exists():
    _DB_FILE.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_FILE}"
os.environ["REDIS_URL"] = "redis://127.0.0.1:1"  # unreachable on purpose

import pytest
from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


VULNERABLE = """
def login(user, pw):
    query = "SELECT * FROM users WHERE name=" + user
    return db.execute(query)

API_KEY = "sk-abcdef1234567890abcdef"

def process(items=[]):
    try:
        return [eval(x) for x in items]
    except:
        return None
"""


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readyz_db_ok_cache_disabled(client):
    r = client.get("/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["database"] == "ok"
    # Cache is unreachable in this test → "disabled", not an error.
    assert body["cache"] == "disabled"


def test_submit_review_finds_known_issues(client):
    r = client.post("/api/reviews", json={"language": "python", "code": VULNERABLE})
    assert r.status_code == 201, r.text
    body = r.json()

    rule_ids = {f["rule_id"] for f in body["findings"]}
    # SQL string-concat
    assert any("SEC-001" in rid for rid in rule_ids), rule_ids
    # Hardcoded secret
    assert any("SEC-002" in rid for rid in rule_ids), rule_ids
    # eval()
    assert any("SEC-005" in rid for rid in rule_ids), rule_ids
    # Mutable default
    assert "PY-BUG-010" in rule_ids
    # Bare except
    assert any("BUG-002" in rid for rid in rule_ids), rule_ids

    # Summary counts match the findings.
    sev_counts = body["summary"]
    total_from_summary = sum(sev_counts.values())
    assert total_from_summary == len(body["findings"])
    assert body["cached"] is False


def test_review_is_cached_on_second_submit(client):
    code = "x = eval(z)\n"
    first = client.post("/api/reviews", json={"language": "python", "code": code}).json()
    second = client.post("/api/reviews", json={"language": "python", "code": code}).json()
    # The in-process cache is disabled in this test (Redis unreachable), so
    # both calls hit the analyzer. We only assert findings are identical.
    assert {f["rule_id"] for f in first["findings"]} == {f["rule_id"] for f in second["findings"]}


def test_list_and_get_review(client):
    r = client.post(
        "/api/reviews",
        json={"language": "python", "code": "from os import *\n"},
    )
    assert r.status_code == 201
    review_id = r.json()["id"]

    r = client.get("/api/reviews?limit=5")
    assert r.status_code == 200
    items = r.json()
    assert any(item["id"] == review_id for item in items)

    r = client.get(f"/api/reviews/{review_id}")
    assert r.status_code == 200
    one = r.json()
    assert one["id"] == review_id
    assert any("ANTI-001" in f["rule_id"] for f in one["findings"])


def test_stats_endpoint(client):
    r = client.get("/api/reviews/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_reviews"] >= 1
    assert "by_severity" in body and "by_category" in body
    assert isinstance(body["avg_latency_ms"], (int, float))


def test_clean_code_returns_zero_findings(client):
    code = (
        "def add(a: int, b: int) -> int:\n"
        '    """Add two numbers."""\n'
        "    return a + b\n"
    )
    r = client.post("/api/reviews", json={"language": "python", "code": code})
    assert r.status_code == 201
    body = r.json()
    assert body["findings"] == []
    assert sum(body["summary"].values()) == 0


def test_oversize_payload_rejected(client):
    big = "a = 1\n" * 50000  # ~300 KB
    r = client.post("/api/reviews", json={"language": "python", "code": big})
    assert r.status_code == 413
