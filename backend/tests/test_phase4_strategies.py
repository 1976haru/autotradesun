"""Phase 4 — 선물 전략 + Council (advisory)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.modes import OperationMode
from app.futures.audit import FuturesOrderAuditLog
from app.futures.auto_loop import FuturesAutoPaperEngine
from app.futures.broker_mock import MockFuturesBroker
from app.futures.contracts.domestic_registry import FuturesContractSpec
from app.futures.risk import FuturesRiskManager, FuturesRiskPolicy
from app.futures.strategies.base import (
    FuturesSignal,
    FuturesSignalAction,
    FuturesStrategyInput,
)
from app.futures.strategies.council import (
    CouncilDecision,
    build_council_decide,
    decision_to_order,
    run_council,
)
from app.futures.strategies.mock_strategies import (
    FuturesTrendFollowingStrategy,
    default_strategies,
)
from app.futures.types import FuturesSide

KST = timezone(timedelta(hours=9))
SPEC = FuturesContractSpec(
    code="KOSPI200_2603", underlying="KOSPI200", display_name="t",
    multiplier=250_000, tick_size_pt=0.05, tick_value_krw=12_500, leverage_max=10.0,
    expiry=datetime(2026, 3, 12, 15, 45, tzinfo=KST),
)


def test_signal_order_intent_invariant():
    with pytest.raises(ValueError):
        FuturesSignal(action=FuturesSignalAction.OPEN_LONG, contract="X", is_order_intent=True)
    with pytest.raises(ValueError):
        FuturesSignal(action=FuturesSignalAction.OPEN_LONG, contract="X", contracts=2)


def test_trend_following_uptrend_signals_open_long():
    closes = list(range(300, 340))  # 꾸준한 상승
    sig = FuturesTrendFollowingStrategy().evaluate(
        FuturesStrategyInput(contract="X", closes=closes)
    )
    assert sig.action == FuturesSignalAction.OPEN_LONG


def test_trend_following_downtrend_signals_open_short():
    closes = list(range(340, 300, -1))
    sig = FuturesTrendFollowingStrategy().evaluate(
        FuturesStrategyInput(contract="X", closes=closes)
    )
    assert sig.action == FuturesSignalAction.OPEN_SHORT


def test_expiring_soon_downgrades_new_entry_to_watch():
    closes = list(range(300, 340))
    sig = FuturesTrendFollowingStrategy().evaluate(
        FuturesStrategyInput(contract="X", closes=closes, expiring_soon=True)
    )
    assert sig.action == FuturesSignalAction.WATCH


def test_council_uptrend_final_open_long():
    data = FuturesStrategyInput(contract="X", closes=list(range(300, 340)))
    decision = run_council(data)
    assert decision.final_action == FuturesSignalAction.OPEN_LONG
    assert decision.long_score > decision.short_score
    assert decision.is_order_intent is False


def test_council_order_intent_invariant():
    with pytest.raises(ValueError):
        CouncilDecision(
            final_action=FuturesSignalAction.OPEN_LONG, contract="X", is_order_intent=True
        )


def test_decision_to_order_mapping():
    long_d = CouncilDecision(final_action=FuturesSignalAction.OPEN_LONG, contract="X")
    short_d = CouncilDecision(final_action=FuturesSignalAction.OPEN_SHORT, contract="X")
    watch_d = CouncilDecision(final_action=FuturesSignalAction.WATCH, contract="X")
    assert decision_to_order(long_d).side == FuturesSide.BUY
    assert decision_to_order(short_d).side == FuturesSide.SELL  # naked short OK (양방향)
    assert decision_to_order(watch_d) is None


def test_council_drives_auto_loop_to_trade():
    # 상승 추세 시세를 주입하기 위해 amplitude 큰 mock 대신 단조 증가 provider 사용
    class _RisingMD:
        def __init__(self):
            self._p = 300

        def get_quote(self, contract, *, now_epoch=None):
            from app.futures.market.futures_market_data import QuoteResult, QuoteStatus
            from app.futures.types import FuturesQuote

            self._p += 1
            return QuoteResult(
                status=QuoteStatus.OK,
                quote=FuturesQuote(
                    contract=contract, price=self._p, timestamp="0",
                    source="mock", epoch=now_epoch or 0.0,
                ),
            )

    b = MockFuturesBroker()
    eng = FuturesAutoPaperEngine(
        mode=OperationMode.SIMULATION, broker=b,
        risk=FuturesRiskManager(FuturesRiskPolicy(max_margin_used=100_000_000)),
        audit=FuturesOrderAuditLog(), market_data=_RisingMD(), spec=SPEC,
        leverage=5.0, decide=build_council_decide(min_bars=21),
    )
    eng.start()
    for i in range(30):
        eng.tick(now_epoch=float(i))
    # 상승 추세 → Council OPEN_LONG → 가상 체결 발생
    assert eng.status().order_count >= 1
    assert len(b.get_positions()) >= 1


def test_strategy_modules_no_execution_imports():
    """advisory 전략/Council 은 broker/executor/router/HTTP 를 *import·호출* 하지 않는다.

    docstring 의 정책 설명(예: 'OrderExecutor 를 import 하지 않는다')은 허용하되,
    실제 import 문 / 호출 패턴만 검사한다.
    """
    import app.futures.strategies.base as base
    import app.futures.strategies.council as council
    import app.futures.strategies.mock_strategies as mock

    forbidden = (
        "broker.place_order",
        "from app.futures.execution",
        "import app.futures.execution",
        "from app.futures.broker_mock",
        "import httpx",
        "import requests",
        ".execute(",
    )
    for mod in (base, council, mock):
        # 코드 라인만 (docstring/주석 # 제외) 검사
        lines = open(mod.__file__, encoding="utf-8").read().splitlines()
        code = "\n".join(
            ln for ln in lines if not ln.lstrip().startswith("#")
        )
        for pat in forbidden:
            assert pat not in code, f"{mod.__name__} contains forbidden pattern {pat!r}"


def test_default_strategies_count():
    assert len(default_strategies()) == 3
