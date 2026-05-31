"""Phase 0 — 앱 기동 + 안전 플래그 기본값 회귀."""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.modes import OperationMode, is_live_mode, is_paper_safe
from app.main import create_app


def test_safety_flag_defaults_are_blocked():
    s = Settings()
    assert s.enable_futures_live_trading is False
    assert s.enable_ai_execution is False
    assert s.default_mode == OperationMode.SIMULATION
    assert s.market_data_provider == "mock"


def test_paper_safe_and_live_mode_classification():
    assert is_paper_safe(OperationMode.SIMULATION)
    assert is_paper_safe(OperationMode.PAPER)
    assert not is_paper_safe(OperationMode.LIVE_MANUAL_APPROVAL)
    assert is_live_mode(OperationMode.LIVE_AI_EXECUTION)
    assert not is_live_mode(OperationMode.SIMULATION)


def test_health_and_status_endpoints():
    client = TestClient(create_app())
    assert client.get("/health").json() == {"status": "ok"}
    body = client.get("/api/status").json()
    assert body["enable_futures_live_trading"] is False
    assert body["is_live_authorization"] is False
    assert body["default_mode"] == "SIMULATION"
