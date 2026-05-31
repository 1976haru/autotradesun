"""단일 주문 진입점 (Phase 3) — route_futures_order.

모든 선물 주문 경로는 이 함수를 통과한다:
1. broker 로 잔고/포지션 조회
2. FuturesRiskManager 평가 (LIVE 모드면 evaluate_order → 항상 REJECTED)
3. FuturesOrderAuditLog 기록 (성공/거부 모두)
4. 분기: REJECTED / NEEDS_APPROVAL / APPROVED(FuturesOrderExecutor.execute)
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.modes import OperationMode, is_paper_safe
from app.futures.audit import FuturesAuditEntry, FuturesOrderAuditLog
from app.futures.broker_mock import MockFuturesBroker
from app.futures.execution.futures_order_executor import FuturesOrderExecutor
from app.futures.risk import FuturesRiskDecision, FuturesRiskManager
from app.futures.types import FuturesOrderRequest, FuturesOrderResult


@dataclass
class RouteOutcome:
    decision: str
    audit: FuturesAuditEntry
    result: FuturesOrderResult | None = None
    reasons: list[str] | None = None
    warnings: list[str] | None = None


def route_futures_order(
    order: FuturesOrderRequest, *,
    mode: OperationMode,
    broker: MockFuturesBroker,
    risk: FuturesRiskManager,
    audit: FuturesOrderAuditLog,
    mark_price: int,
    multiplier: int,
    leverage: float,
    source: str = "STRATEGY",
    contract_leverage_max: float | None = None,
    price_age_seconds: float | None = None,
    stale_max_age_seconds: int | None = None,
) -> RouteOutcome:
    # LIVE 모드 — 본 빌드에서 항상 REJECTED.
    if not is_paper_safe(mode):
        res = risk.evaluate_order()
        entry = audit.record(
            contract=order.contract, side=order.side.value, quantity=order.quantity,
            decision=res.decision.value, mode=mode.value, source=source, reasons=res.reasons,
        )
        return RouteOutcome(decision=res.decision.value, audit=entry, reasons=res.reasons)

    balance = broker.get_balance()
    positions = broker.get_positions()
    res = risk.evaluate_virtual_order(
        order=order, positions=positions,
        margin_used=balance.margin_used, margin_available=balance.margin_available,
        mark_price=mark_price, multiplier=multiplier, leverage=leverage,
        contract_leverage_max=contract_leverage_max,
        price_age_seconds=price_age_seconds, stale_max_age_seconds=stale_max_age_seconds,
    )

    if res.decision == FuturesRiskDecision.REJECTED:
        entry = audit.record(
            contract=order.contract, side=order.side.value, quantity=order.quantity,
            decision="REJECTED", mode=mode.value, source=source,
            reasons=res.reasons, warnings=res.warnings,
        )
        return RouteOutcome(
            decision="REJECTED", audit=entry, reasons=res.reasons, warnings=res.warnings
        )

    if res.decision == FuturesRiskDecision.NEEDS_APPROVAL:
        entry = audit.record(
            contract=order.contract, side=order.side.value, quantity=order.quantity,
            decision="NEEDS_APPROVAL", mode=mode.value, source=source,
            reasons=res.reasons, warnings=res.warnings,
        )
        return RouteOutcome(
            decision="NEEDS_APPROVAL", audit=entry, reasons=res.reasons, warnings=res.warnings
        )

    # APPROVED — executor 가 broker.place_order 호출 (유일한 fill 경로)
    result = FuturesOrderExecutor(broker).execute(
        order, decision="APPROVED", mark_price=mark_price, multiplier=multiplier,
        leverage=leverage,
    )
    entry = audit.record(
        contract=order.contract, side=order.side.value, quantity=order.quantity,
        decision="APPROVED", mode=mode.value, source=source, warnings=res.warnings,
        order_id=result.order_id, filled_quantity=result.filled_quantity,
        avg_fill_price=result.avg_fill_price,
    )
    return RouteOutcome(decision="APPROVED", audit=entry, result=result, warnings=res.warnings)
