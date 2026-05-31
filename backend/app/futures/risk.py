"""FuturesRiskManager (Phase 3) — 선물 주문 평가.

- `enable_futures_live_trading=False` → LIVE 평가(`evaluate_order`)는 모든 주문 REJECTED.
  True 여도 본 빌드는 LIVE 미구현 → 여전히 REJECTED.
- 가상(SIMULATION/PAPER) 평가는 `evaluate_virtual_order` — LIVE 플래그와 무관하게 작동.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.futures.margin_rules import (
    FuturesMarginRule,
    LeverageLimitRule,
    LiquidationRiskRule,
    MarginRuleDecision,
)
from app.futures.types import FuturesOrderRequest, FuturesPosition


class FuturesRiskDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"


@dataclass
class FuturesRiskPolicy:
    """보수적 기본값 — 선물은 레버리지/오버나이트 위험으로 주식보다 타이트."""

    max_contracts: int = 1
    max_margin_used: int = 1_000_000
    max_daily_loss: int = 200_000
    max_leverage: float = 10.0
    enable_futures_live_trading: bool = False
    maintenance_margin_pct: float = 10.0
    liquidation_critical_pct: float = 3.0
    liquidation_warning_pct: float = 7.0


@dataclass
class FuturesRiskCheckResult:
    decision: FuturesRiskDecision
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


class FuturesRiskManager:
    def __init__(self, policy: FuturesRiskPolicy | None = None, *, daily_realized_pnl: int = 0):
        self.policy = policy or FuturesRiskPolicy()
        self.daily_realized_pnl = daily_realized_pnl

    # ---- LIVE evaluation (항상 REJECTED — 본 빌드 비활성) ----

    def evaluate_order(self, **_kwargs) -> FuturesRiskCheckResult:
        if not self.policy.enable_futures_live_trading:
            return FuturesRiskCheckResult(
                decision=FuturesRiskDecision.REJECTED,
                reasons=["ENABLE_FUTURES_LIVE_TRADING is disabled"],
            )
        return FuturesRiskCheckResult(
            decision=FuturesRiskDecision.REJECTED,
            reasons=["live futures evaluation not implemented in this build"],
        )

    # ---- virtual evaluation (SIMULATION / PAPER) ----

    def evaluate_virtual_order(
        self, *,
        order: FuturesOrderRequest,
        positions: list[FuturesPosition],
        margin_used: int,
        margin_available: int,
        mark_price: int,
        multiplier: int,
        leverage: float,
        contract_leverage_max: float | None = None,
        price_age_seconds: float | None = None,
        stale_max_age_seconds: int | None = None,
    ) -> FuturesRiskCheckResult:
        result = FuturesRiskCheckResult(decision=FuturesRiskDecision.APPROVED)

        # 0. stale price hard-reject
        if (
            stale_max_age_seconds is not None
            and price_age_seconds is not None
            and price_age_seconds > stale_max_age_seconds
        ):
            result.reasons.append(
                f"stale price: {price_age_seconds:.0f}s > {stale_max_age_seconds}s"
            )

        # 1. leverage
        lev = LeverageLimitRule(self.policy.max_leverage, contract_leverage_max).check(leverage)
        if lev.decision == MarginRuleDecision.BLOCK:
            result.reasons.extend(lev.reasons)
        result.metrics.update(lev.metrics)

        # 2. contract count
        existing = sum(p.quantity for p in positions if p.contract == order.contract)
        new_total = existing + order.quantity
        if new_total > self.policy.max_contracts:
            result.reasons.append(
                f"contracts {new_total} exceeds max_contracts {self.policy.max_contracts}"
            )
        result.metrics["contracts_after"] = new_total

        # 3. mark price guard
        if mark_price <= 0:
            result.reasons.append("mark_price must be positive")

        # 4. margin + 5. liquidation
        if mark_price > 0 and leverage > 0:
            mres = FuturesMarginRule(
                self.policy.max_margin_used, self.policy.maintenance_margin_pct
            ).check(
                order=order, margin_used=margin_used, margin_available=margin_available,
                mark_price=mark_price, multiplier=multiplier, leverage=leverage,
            )
            if mres.decision == MarginRuleDecision.BLOCK:
                result.reasons.extend(mres.reasons)
            elif mres.decision == MarginRuleDecision.WARN:
                result.warnings.extend(mres.warnings)
            result.metrics.update(mres.metrics)

            lres = LiquidationRiskRule(
                self.policy.liquidation_critical_pct,
                self.policy.liquidation_warning_pct,
                self.policy.maintenance_margin_pct,
            ).check(order=order, positions=positions, mark_price=mark_price, leverage=leverage)
            if lres.decision == MarginRuleDecision.BLOCK:
                result.reasons.extend(lres.reasons)
            elif lres.decision == MarginRuleDecision.WARN:
                result.warnings.extend(lres.warnings)
            for k, v in lres.metrics.items():
                result.metrics.setdefault(k, v)

        # 6. daily loss
        if self.daily_realized_pnl <= -abs(self.policy.max_daily_loss):
            result.reasons.append("daily futures loss limit reached")

        if result.reasons:
            result.decision = FuturesRiskDecision.REJECTED
        return result
