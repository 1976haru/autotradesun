"""FuturesOrderExecutor (Phase 3) — broker.place_order 를 호출하는 *유일한* 코드.

router 가 RiskManager 평가 결과 APPROVED 일 때만 execute 를 호출한다. executor 는
decision 이 APPROVED 가 아니거나 broker 가 live 이면 즉시 거부(backstop).
"""

from __future__ import annotations

from app.futures.broker_mock import MockFuturesBroker
from app.futures.types import FuturesOrderRequest, FuturesOrderResult


class UnauthorizedFuturesOrderError(RuntimeError):
    pass


class FuturesOrderExecutor:
    def __init__(self, broker: MockFuturesBroker):
        self.broker = broker

    def execute(
        self, order: FuturesOrderRequest, *,
        decision: str, mark_price: int, multiplier: int, leverage: float,
    ) -> FuturesOrderResult:
        if decision != "APPROVED":
            raise UnauthorizedFuturesOrderError(
                f"executor refused: decision={decision} (only APPROVED proceeds)"
            )
        if getattr(self.broker, "is_live", False):
            raise UnauthorizedFuturesOrderError("executor refused: broker is live")
        return self.broker.place_order(
            order, mark_price=mark_price, multiplier=multiplier, leverage=leverage
        )
