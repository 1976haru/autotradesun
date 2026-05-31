"""선물 Agent Council (Phase 4) — advisory 신호 통합기.

3개 mock 전략의 신호를 가중 투표로 통합해 final_action 을 산출한다. **주문 의도가
아니다** — `CouncilDecision.is_order_intent=False` 불변. `build_council_decide()` 는
auto-loop 가 쓰는 decide 콜백(가격 히스토리 누적 + Council 실행 + 주문 매핑)을 만든다.

본 모듈은 broker / OrderExecutor / order_router 를 import 하지 않는다 (정적 grep 가드).
주문 매핑 결과는 단순 `FuturesOrderRequest` *후보*이며, 실제 실행은 router 가 한다.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from app.futures.strategies.base import (
    FuturesSignal,
    FuturesSignalAction,
    FuturesStrategyBase,
    FuturesStrategyInput,
)
from app.futures.strategies.mock_strategies import default_strategies
from app.futures.types import FuturesOrderRequest, FuturesSide

# action → 방향 점수 (롱 +1 / 숏 -1 / 중립 0)
_LONG_ACTIONS = {FuturesSignalAction.OPEN_LONG, FuturesSignalAction.CLOSE_SHORT}
_SHORT_ACTIONS = {FuturesSignalAction.OPEN_SHORT, FuturesSignalAction.CLOSE_LONG}


@dataclass
class CouncilDecision:
    final_action: FuturesSignalAction
    contract: str
    confidence: int = 0
    long_score: float = 0.0
    short_score: float = 0.0
    selected: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    is_order_intent: bool = False  # 불변 — Council 은 주문 의도가 아님

    def __post_init__(self) -> None:
        if self.is_order_intent:
            raise ValueError("CouncilDecision.is_order_intent must be False (advisory only)")


def run_council(
    data: FuturesStrategyInput, strategies: list[FuturesStrategyBase] | None = None
) -> CouncilDecision:
    strategies = strategies or default_strategies()
    long_score = 0.0
    short_score = 0.0
    selected: list[str] = []
    reasons: list[str] = []
    for strat in strategies:
        sig: FuturesSignal = strat.evaluate(data)
        if sig.action == FuturesSignalAction.NO_SIGNAL:
            continue
        w = sig.confidence / 100.0
        if sig.action in _LONG_ACTIONS:
            long_score += w
            selected.append(strat.name)
            reasons.append(f"{strat.name}: {sig.action.value} ({sig.reason})")
        elif sig.action in _SHORT_ACTIONS:
            short_score += w
            selected.append(strat.name)
            reasons.append(f"{strat.name}: {sig.action.value} ({sig.reason})")

    # 만기 임박 시 신규 진입 억제 (보유 청산은 허용)
    pos = data.position_side
    if long_score == 0 and short_score == 0:
        return CouncilDecision(
            final_action=FuturesSignalAction.WATCH, contract=data.contract,
            long_score=0, short_score=0, reasons=reasons or ["no directional votes"],
        )

    if long_score > short_score:
        action = FuturesSignalAction.CLOSE_SHORT if pos == "SHORT" else FuturesSignalAction.OPEN_LONG
        conf = min(95, int(long_score / max(1, len(strategies)) * 100))
    elif short_score > long_score:
        action = FuturesSignalAction.CLOSE_LONG if pos == "LONG" else FuturesSignalAction.OPEN_SHORT
        conf = min(95, int(short_score / max(1, len(strategies)) * 100))
    else:
        action = FuturesSignalAction.WATCH
        conf = 0

    if data.expiring_soon and action in (
        FuturesSignalAction.OPEN_LONG, FuturesSignalAction.OPEN_SHORT
    ):
        action = FuturesSignalAction.WATCH
        reasons.append("expiring soon — new entry downgraded to WATCH (rollover advisory)")

    return CouncilDecision(
        final_action=action, contract=data.contract, confidence=conf,
        long_score=long_score, short_score=short_score, selected=selected, reasons=reasons,
    )


def decision_to_order(decision: CouncilDecision) -> FuturesOrderRequest | None:
    """Council final_action → 주문 *후보* (router 가 실행). 무신호면 None."""
    a = decision.final_action
    if a == FuturesSignalAction.OPEN_LONG or a == FuturesSignalAction.CLOSE_SHORT:
        return FuturesOrderRequest(
            contract=decision.contract, side=FuturesSide.BUY, quantity=1,
            strategy="council", trade_reason=a.value,
        )
    if a == FuturesSignalAction.OPEN_SHORT or a == FuturesSignalAction.CLOSE_LONG:
        return FuturesOrderRequest(
            contract=decision.contract, side=FuturesSide.SELL, quantity=1,
            strategy="council", trade_reason=a.value,
        )
    return None


def build_council_decide(*, history: int = 30, min_bars: int = 21):
    """auto-loop decide 콜백 생성 — 가격 히스토리 누적 + Council 실행 + 주문 매핑."""
    closes: dict[str, deque] = defaultdict(lambda: deque(maxlen=history))

    def _decide(contract, quote, positions):
        closes[contract].append(quote.price)
        if len(closes[contract]) < min_bars:
            return None
        pos_side = None
        for p in positions:
            if p.contract == contract:
                pos_side = p.side.value
                break
        data = FuturesStrategyInput(
            contract=contract, closes=list(closes[contract]), position_side=pos_side,
        )
        decision = run_council(data)
        order = decision_to_order(decision)
        # 이미 같은 방향 보유 시 추가 진입 억제 (계약 한도 1)
        if order is not None and pos_side is not None:
            from app.futures.types import FuturesSide as _S

            if (pos_side == "LONG" and order.side == _S.BUY) or (
                pos_side == "SHORT" and order.side == _S.SELL
            ):
                return None
        return order

    return _decide
