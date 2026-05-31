"""FuturesAutoPaperEngine (Phase 3) — 모의/Paper 자동매매 루프 ("시작 버튼" 백엔드).

start/stop/status + tick 마다: 시세 수신 → broker mark 갱신 → 전략(decide 콜백)
신호 → route_futures_order(RiskManager → audit → 가상 체결) → 포지션/손익 갱신.

SIMULATION / PAPER 전용 — `is_paper_safe(mode)` 아니면 start 거부.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.modes import OperationMode, is_paper_safe
from app.futures.audit import FuturesOrderAuditLog
from app.futures.broker_mock import MockFuturesBroker
from app.futures.contracts.domestic_registry import FuturesContractSpec
from app.futures.execution.futures_order_router import RouteOutcome, route_futures_order
from app.futures.market.futures_market_data import QuoteStatus
from app.futures.risk import FuturesRiskManager
from app.futures.types import FuturesOrderRequest, FuturesPosition, FuturesQuote

DecideFn = Callable[[str, FuturesQuote, list[FuturesPosition]], FuturesOrderRequest | None]


@dataclass
class LoopStatus:
    running: bool
    mode: str
    contract: str
    tick_count: int
    order_count: int
    reject_count: int
    last_reasons: list[str] = field(default_factory=list)
    last_price: int | None = None
    blocked_reason: str | None = None


class FuturesAutoPaperEngine:
    def __init__(
        self, *,
        mode: OperationMode,
        broker: MockFuturesBroker,
        risk: FuturesRiskManager,
        audit: FuturesOrderAuditLog,
        market_data,
        spec: FuturesContractSpec,
        leverage: float = 5.0,
        decide: DecideFn | None = None,
        stale_max_age_seconds: int | None = None,
    ):
        self.mode = mode
        self.broker = broker
        self.risk = risk
        self.audit = audit
        self.market_data = market_data
        self.spec = spec
        self.leverage = leverage
        self.decide = decide
        self.stale_max_age_seconds = stale_max_age_seconds
        self._running = False
        self._tick_count = 0
        self._order_count = 0
        self._reject_count = 0
        self._last_reasons: list[str] = []
        self._last_price: int | None = None

    def start(self) -> LoopStatus:
        if not is_paper_safe(self.mode):
            return self.status(blocked_reason="mode is not paper-safe (live blocked)")
        self._running = True
        return self.status()

    def stop(self) -> LoopStatus:
        self._running = False
        return self.status()

    def status(self, *, blocked_reason: str | None = None) -> LoopStatus:
        return LoopStatus(
            running=self._running, mode=self.mode.value, contract=self.spec.code,
            tick_count=self._tick_count, order_count=self._order_count,
            reject_count=self._reject_count, last_reasons=self._last_reasons,
            last_price=self._last_price, blocked_reason=blocked_reason,
        )

    def tick(self, *, now_epoch: float | None = None) -> RouteOutcome | None:
        if not self._running:
            return None
        self._tick_count += 1

        qr = self.market_data.get_quote(self.spec.code, now_epoch=now_epoch)
        if qr.status != QuoteStatus.OK or qr.quote is None:
            self._last_reasons = [f"quote unavailable: {qr.status.value} {qr.reason}".strip()]
            return None
        quote = qr.quote
        self._last_price = quote.price
        self.broker.set_mark(self.spec.code, quote.price)

        if self.decide is None:
            return None
        order = self.decide(self.spec.code, quote, self.broker.get_positions())
        if order is None:
            return None

        age = None
        if quote.epoch is not None:
            cur = now_epoch if now_epoch is not None else time.time()
            age = max(0.0, cur - quote.epoch)

        outcome = route_futures_order(
            order, mode=self.mode, broker=self.broker, risk=self.risk, audit=self.audit,
            mark_price=quote.price, multiplier=self.spec.multiplier, leverage=self.leverage,
            source="AUTO_LOOP", contract_leverage_max=self.spec.leverage_max,
            price_age_seconds=age, stale_max_age_seconds=self.stale_max_age_seconds,
        )
        if outcome.decision == "APPROVED":
            self._order_count += 1
        elif outcome.decision == "REJECTED":
            self._reject_count += 1
            self._last_reasons = outcome.reasons or []
        return outcome
