"""Phase 3 — 선물 API 엔드포인트 (시작/중지/상태/포지션/감사)."""

import importlib

from fastapi.testclient import TestClient

from app.main import create_app


def _client():
    import app.api.routes_futures as rf

    importlib.reload(rf)
    return TestClient(create_app())


def test_contracts_endpoint_lists_products():
    assert len(_client().get("/api/futures/contracts").json()["contracts"]) == 3


def test_start_runs_and_status_reflects_running():
    c = _client()
    started = c.post("/api/futures/auto/start").json()
    assert started["running"] is True
    assert started["is_live_authorization"] is False
    assert started["tick_count"] >= 1
    assert c.get("/api/futures/auto/status").json()["running"] is True


def test_start_then_audit_records_present():
    c = _client()
    c.post("/api/futures/auto/start")
    # Council 은 가격 히스토리(≥21봉) 누적 후 신호 — 충분히 tick 한다.
    for _ in range(60):
        c.post("/api/futures/auto/tick")
    assert c.get("/api/futures/audit").json()["count"] >= 1
    pos = c.get("/api/futures/positions").json()
    assert "balance" in pos


def test_stop_sets_running_false():
    c = _client()
    c.post("/api/futures/auto/start")
    assert c.post("/api/futures/auto/stop").json()["running"] is False
