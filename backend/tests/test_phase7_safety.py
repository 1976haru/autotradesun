"""Phase 7 — 안전 가드 회귀 + 정적 grep 가드 + preflight."""

import pathlib

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.futures.preflight import run_preflight
from app.main import create_app

APP_DIR = pathlib.Path(__file__).resolve().parents[1] / "app"

# advisory / 비실행 모듈 — broker/executor/router/HTTP/AI SDK import 금지
ADVISORY_MODULES = [
    "futures/strategies/base.py",
    "futures/strategies/mock_strategies.py",
    "futures/strategies/council.py",
    "futures/backtest/metrics.py",
    "futures/backtest/engine.py",
    "futures/backtest/walk_forward.py",
    "futures/contracts/domestic_registry.py",
    "futures/market/futures_market_data.py",
]

FORBIDDEN_IN_ADVISORY = [
    "from app.futures.execution",
    "import app.futures.execution",
    "broker.place_order",
    "import httpx",
    "import requests",
    "import anthropic",
    "import openai",
]


def _code_lines(path: pathlib.Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(ln for ln in lines if not ln.lstrip().startswith("#"))


def test_advisory_modules_have_no_execution_or_network_imports():
    for rel in ADVISORY_MODULES:
        code = _code_lines(APP_DIR / rel)
        for pat in FORBIDDEN_IN_ADVISORY:
            assert pat not in code, f"{rel} contains forbidden {pat!r}"


def test_safety_flag_defaults_blocked():
    s = Settings()
    assert s.enable_futures_live_trading is False
    assert s.enable_ai_execution is False
    assert s.default_mode.value in ("SIMULATION", "PAPER")
    assert s.market_data_provider == "mock"


def test_preflight_passes_with_safe_defaults():
    rep = run_preflight(Settings())
    assert rep.ok is True
    assert rep.is_live_authorization is False
    names = {c.name for c in rep.checks}
    assert "enable_futures_live_trading" in names
    assert "broker_paper_safe" in names


def test_preflight_fails_when_live_enabled():
    s = Settings(enable_futures_live_trading=True)
    rep = run_preflight(s)
    assert rep.ok is False


def test_preflight_endpoint_read_only():
    c = TestClient(create_app())
    body = c.get("/api/futures/preflight").json()
    assert body["is_live_authorization"] is False
    assert "checks" in body
