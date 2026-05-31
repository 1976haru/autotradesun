"""FuturesStrategyBase contract (Phase 4) — advisory only.

선물 전략의 공식 ABC. 양방향(LONG/SHORT) 진입을 명시 표현한다. 모든 신호는
*추천*이며 `is_order_intent=False` 불변 — 실제 주문은 RiskManager + 단일 진입점
router 를 통과한 뒤에만 만들어진다.

절대 invariant (테스트로 강제):
- 본 모듈은 broker / OrderExecutor / order_router / market data import 0건.
- FuturesSignal.is_order_intent 는 항상 False (True 생성 시 ValueError).
- 본 ABC 는 어떤 주식 Strategy 도 상속하지 않는다 (독립 계층).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum


class FuturesSignalAction(StrEnum):
    OPEN_LONG = "OPEN_LONG"
    OPEN_SHORT = "OPEN_SHORT"
    CLOSE_LONG = "CLOSE_LONG"
    CLOSE_SHORT = "CLOSE_SHORT"
    REDUCE_SIZE = "REDUCE_SIZE"
    HEDGE = "HEDGE"
    ROLLOVER = "ROLLOVER"
    WATCH = "WATCH"
    NO_SIGNAL = "NO_SIGNAL"


@dataclass(frozen=True)
class FuturesSignal:
    action: FuturesSignalAction
    contract: str
    confidence: int = 50
    contracts: int = 1
    reason: str = ""
    is_order_intent: bool = False

    def __post_init__(self) -> None:
        if self.is_order_intent:
            raise ValueError("FuturesSignal.is_order_intent must be False (advisory only)")
        if self.contracts > 1:
            raise ValueError("contracts must be <= 1 in mock phase")
        if not (0 <= self.confidence <= 100):
            raise ValueError("confidence must be 0..100")


@dataclass
class FuturesStrategyInput:
    contract: str
    closes: list[int] = field(default_factory=list)   # 오래된 → 최신
    position_side: str | None = None                  # "LONG" / "SHORT" / None
    expiring_soon: bool = False


class FuturesStrategyBase(ABC):
    """선물 전략 ABC — 주식 Strategy 를 상속하지 않는 독립 계층."""

    name: str = "futures_strategy"

    @abstractmethod
    def evaluate(self, data: FuturesStrategyInput) -> FuturesSignal:
        raise NotImplementedError

    def _no_signal(self, contract: str, reason: str = "insufficient data") -> FuturesSignal:
        return FuturesSignal(
            action=FuturesSignalAction.NO_SIGNAL, contract=contract, confidence=0, reason=reason
        )
