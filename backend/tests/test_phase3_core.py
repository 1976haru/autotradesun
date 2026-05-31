"""Phase 3 — risk / broker / router(단일 진입점) / executor / auto-loop e2e."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.modes import OperationMode
from app.futures.audit import FuturesOrderAuditLog
from app.futures.auto_loop import FuturesAutoPaperEngine
from app.futures.broker_mock import MockFuturesBroker
from app.futures.contracts.domestic_registry import FuturesContractSpec
from app.futures.execution.futures_order_executor import (
    FuturesOrderExecutor,
    UnauthorizedFuturesOrderError,
)
from app.futures.execution.futures_order_router import route_futures_order
from app.futures.market.futures_market_data import MockFuturesMarketData
from app.futures.risk import FuturesRiskDecision, FuturesRiskManager, FuturesRiskPolicy
from app.futures.types import FuturesOrderRequest, FuturesPositionSide, FuturesSide

KST = timezone(timedelta(hours=9))
SPEC = FuturesContractSpec(
    code="KOSPI200_2603", underlying="KOSPI200", display_name="t",
    multiplier=250_000, tick_size_pt=0.05, tick_value_krw=12_500, leverage_max=10.0,
    expiry=datetime(2026, 3, 12, 15, 45, tzinfo=KST),
)


def _order(side=FuturesSide.BUY, qty=1):
    return FuturesOrderRequest(contract=SPEC.code, side=side, quantity=qty, strategy="t")


def test_virtual_order_approved_within_limits():
    rm = FuturesRiskManager(FuturesRiskPolicy(max_contracts=1, max_margin_used=100_000_000))
    res = rm.evaluate_virtual_order(
        order=_order(), positions=[], margin_used=0, margin_available=10_000_000,
        mark_price=350, multiplier=250_000, leverage=5.0,
    )
    assert res.decision == FuturesRiskDecision.APPROVED


def test_virtual_order_rejected_over_contract_limit():
    rm = FuturesRiskManager(FuturesRiskPolicy(max_contracts=1))
    res = rm.evaluate_virtual_order(
        order=_order(qty=2), positions=[], margin_used=0, margin_available=10_000_000,
        mark_price=350, multiplier=250_000, leverage=5.0,
    )
    assert res.decision == FuturesRiskDecision.REJECTED
    assert any("contracts" in r for r in res.reasons)


def test_virtual_order_rejected_over_leverage():
    rm = FuturesRiskManager(FuturesRiskPolicy(max_leverage=10.0))
    res = rm.evaluate_virtual_order(
        order=_order(), positions=[], margin_used=0, margin_available=10_000_000,
        mark_price=350, multiplier=250_000, leverage=50.0,
    )
    assert res.decision == FuturesRiskDecision.REJECTED
    assert any("leverage" in r for r in res.reasons)


def test_virtual_order_rejected_on_stale_price():
    rm = FuturesRiskManager(FuturesRiskPolicy(max_margin_used=100_000_000))
    res = rm.evaluate_virtual_order(
        order=_order(), positions=[], margin_used=0, margin_available=10_000_000,
        mark_price=350, multiplier=250_000, leverage=5.0,
        price_age_seconds=120, stale_max_age_seconds=60,
    )
    assert res.decision == FuturesRiskDecision.REJECTED
    assert any("stale" in r for r in res.reasons)


def test_live_evaluate_always_rejected():
    assert FuturesRiskManager(
        FuturesRiskPolicy(enable_futures_live_trading=False)
    ).evaluate_order().decision == FuturesRiskDecision.REJECTED
    assert FuturesRiskManager(
        FuturesRiskPolicy(enable_futures_live_trading=True)
    ).evaluate_order().decision == FuturesRiskDecision.REJECTED


def test_broker_fill_opens_and_closes_position_with_pnl():
    b = MockFuturesBroker(initial_cash=10_000_000)
    r = b.place_order(_order(FuturesSide.BUY, 1), mark_price=350, multiplier=250_000, leverage=5.0)
    assert r.filled_quantity == 1
    pos = b.get_positions()[0]
    assert pos.side == FuturesPositionSide.LONG and pos.quantity == 1
    b.set_mark(SPEC.code, 360)
    b.place_order(_order(FuturesSide.SELL, 1), mark_price=360, multiplier=250_000, leverage=5.0)
    assert b.get_positions() == []
    assert b.realized_pnl == 2_500_000  # (360-350)*1*250000
    assert b.cash == 10_000_000 + 2_500_000


def test_router_approved_fills_and_audits():
    b = MockFuturesBroker()
    audit = FuturesOrderAuditLog()
    out = route_futures_order(
        _order(), mode=OperationMode.SIMULATION, broker=b,
        risk=FuturesRiskManager(FuturesRiskPolicy(max_margin_used=100_000_000)), audit=audit,
        mark_price=350, multiplier=250_000, leverage=5.0,
    )
    assert out.decision == "APPROVED"
    assert out.result is not None and out.result.filled_quantity == 1
    assert audit.count() == 1
    assert audit.entries()[0].actual_broker_order_sent is False


def test_router_live_mode_rejects_and_audits_no_fill():
    b = MockFuturesBroker()
    audit = FuturesOrderAuditLog()
    out = route_futures_order(
        _order(), mode=OperationMode.LIVE_MANUAL_APPROVAL, broker=b,
        risk=FuturesRiskManager(), audit=audit,
        mark_price=350, multiplier=250_000, leverage=5.0,
    )
    assert out.decision == "REJECTED"
    assert out.result is None
    assert b.get_positions() == []
    assert audit.count() == 1


def test_executor_refuses_non_approved():
    ex = FuturesOrderExecutor(MockFuturesBroker())
    with pytest.raises(UnauthorizedFuturesOrderError):
        ex.execute(_order(), decision="REJECTED", mark_price=350, multiplier=250_000, leverage=5.0)


def _always_buy_once(contract, quote, positions):
    if positions:
        return None
    return FuturesOrderRequest(contract=contract, side=FuturesSide.BUY, quantity=1, strategy="t")


def test_auto_loop_one_cycle_fills_in_paper():
    b = MockFuturesBroker()
    eng = FuturesAutoPaperEngine(
        mode=OperationMode.SIMULATION, broker=b,
        risk=FuturesRiskManager(FuturesRiskPolicy(max_margin_used=100_000_000)),
        audit=FuturesOrderAuditLog(),
        market_data=MockFuturesMarketData(base_price=350), spec=SPEC,
        leverage=5.0, decide=_always_buy_once,
    )
    assert eng.start().running is True
    out = eng.tick(now_epoch=1000.0)
    assert out is not None and out.decision == "APPROVED"
    st = eng.status()
    assert st.order_count == 1 and st.tick_count == 1
    assert len(b.get_positions()) == 1


def test_auto_loop_start_blocked_in_live_mode():
    eng = FuturesAutoPaperEngine(
        mode=OperationMode.LIVE_AI_EXECUTION, broker=MockFuturesBroker(),
        risk=FuturesRiskManager(), audit=FuturesOrderAuditLog(),
        market_data=MockFuturesMarketData(), spec=SPEC, decide=_always_buy_once,
    )
    st = eng.start()
    assert st.running is False and st.blocked_reason is not None
    assert eng.tick(now_epoch=1000.0) is None


def test_auto_loop_stop_idempotent():
    eng = FuturesAutoPaperEngine(
        mode=OperationMode.SIMULATION, broker=MockFuturesBroker(),
        risk=FuturesRiskManager(FuturesRiskPolicy(max_margin_used=100_000_000)),
        audit=FuturesOrderAuditLog(), market_data=MockFuturesMarketData(), spec=SPEC,
        decide=_always_buy_once,
    )
    eng.start()
    eng.stop()
    assert eng.stop().running is False
    assert eng.tick(now_epoch=1000.0) is None
