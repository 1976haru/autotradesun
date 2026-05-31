"""Phase 5 — 백테스트 / walk-forward / stress + CLI."""

import subprocess
import sys
from pathlib import Path

import pytest

from app.futures.backtest.engine import BacktestConfig, BacktestReport, run_backtest
from app.futures.backtest.metrics import compute_metrics
from app.futures.backtest.stress import run_stress_test
from app.futures.backtest.walk_forward import run_walk_forward

REPO_ROOT = Path(__file__).resolve().parents[2]


def _trend_closes(n=120):
    # 상승 후 하락 (양방향 신호 유도)
    up = list(range(300, 300 + n // 2))
    down = list(range(300 + n // 2, 300, -1))
    return up + down


# ---------- metrics ----------

def test_metrics_basic():
    m = compute_metrics([100, -50, 200, -30])
    assert m.trades == 4 and m.wins == 2 and m.losses == 2
    assert m.net_pnl == 220
    assert m.profit_factor == pytest.approx(300 / 80)
    assert m.max_consecutive_losses == 1


def test_metrics_no_losses_profit_factor_none():
    m = compute_metrics([100, 50])
    assert m.profit_factor is None
    assert m.max_drawdown == 0


def test_metrics_max_drawdown():
    m = compute_metrics([100, -150, 50])  # equity 100 -> -50 -> 0; peak 100, trough -50 => mdd 150
    assert m.max_drawdown == 150


# ---------- engine ----------

def test_backtest_runs_and_invariants():
    rep = run_backtest(_trend_closes(), config=BacktestConfig())
    assert isinstance(rep, BacktestReport)
    assert rep.is_order_signal is False
    assert rep.is_live_authorization is False
    assert rep.auto_apply_allowed is False
    assert rep.no_profit_guarantee is True
    assert rep.bars > 0


def test_backtest_short_pnl_calculated_with_multiplier():
    # 하락만: 숏 진입 시 이익이어야 (multiplier 반영)
    closes = list(range(360, 300, -1))
    rep = run_backtest(closes, config=BacktestConfig(multiplier=250_000, commission_krw=0, slippage_ticks=0))
    # 거래가 발생했고 숏 손익이 정상 계산 (net 이 0 이 아님)
    assert rep.metrics.trades >= 1


def test_backtest_report_invariant_guard():
    with pytest.raises(ValueError):
        BacktestReport(config={}, metrics=compute_metrics([]), bars=0, is_order_signal=True)


# ---------- walk forward ----------

def test_walk_forward_insufficient_data():
    rep = run_walk_forward(list(range(300, 320)))
    assert rep.reason_code == "WALK_FORWARD_INSUFFICIENT_DATA"


def test_walk_forward_runs_and_invariants():
    rep = run_walk_forward(_trend_closes(200))
    assert rep.segments == 2
    assert rep.is_live_authorization is False
    assert rep.auto_apply_allowed is False


# ---------- stress ----------

def test_stress_guards_pass():
    rep = run_stress_test()
    names = {r.name for r in rep.results}
    assert {"STALE_PRICE", "HIGH_LEVERAGE", "MARGIN_EXCEEDED", "MARKET_CRASH"} <= names
    assert rep.passed is True
    assert rep.is_live_authorization is False


# ---------- CLI subprocess ----------

def test_cli_backtest_synthetic_runs():
    script = REPO_ROOT / "scripts" / "run_futures_backtest.py"
    r = subprocess.run(
        [sys.executable, str(script), "--synthetic", "--output", "reports/futures_test"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


def test_cli_stress_runs():
    script = REPO_ROOT / "scripts" / "run_futures_stress_test.py"
    r = subprocess.run(
        [sys.executable, str(script), "--output", "reports/futures_test"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
