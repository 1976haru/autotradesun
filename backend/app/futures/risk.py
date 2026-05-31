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
    max_margin_used: int = 30_000_000
    max_daily_loss: int = 2_000_000
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

    def evaluate_order(self, **_kwargs) -> FuturesRiskCheckResult:
        """LIVE 평가 — 항상 REJECTED (본 빌드 비활성)."""
        if not self.policy.enable_futures_live_trading:
            return FuturesRiskCheckResult(
                decision=FuturesRiskDecision.REJECTED,
                reasons=["ENABLE_FUTURES_LIVE_TRADING is disabled"],
            )
        return FuturesRiskCheckResult(
            decision=FuturesRiskDecision.REJECTED,
            reasons=["live futures evaluation not implemented in this build"],
        )

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
        reasons: list[str] = []
        warnings: list[str] = []
        metrics: dict = {}

        # 0. stale price hard-reject
        if (
            stale_max_age_seconds is not None
            and price_age_seconds is not None
            and price_age_seconds > stale_max_age_seconds
        ):
            reasons.append(f"stale price: {price_age_seconds:.0f}s > {stale_max_age_seconds}s")

        # 1. leverage
        lev = LeverageLimitRule(self.policy.max_leverage, contract_leverage_max).check(leverage)
        if lev.decision == MarginRuleDecision.BLOCK:
            reasons.extend(lev.reasons)
        metrics.update(lev.metrics)

        # 2. contract count
        existing = sum(p.quantity for p in positions if p.contract == order.contract)
        new_total = existing + order.quantity
        if new_total > self.policy.max_contracts:
            reasons.append(
                f"contracts {new_total} exceeds max_contracts {self.policy.max_contracts}"
            )
        metrics["contracts_after"] = new_total

        # 3. mark price guard
        valid_price = mark_price > 0
        if not valid_price:
            reasons.append("mark_price must be positive")

        # 4. margin + 5. liquidation (유효 가격/레버리지일 때만)
        if valid_price and leverage > 0:
            mres = FuturesMarginRule(
                self.policy.max_margin_used, self.policy.maintenance_margin_pct
            ).check(
                order=order, margin_used=margin_used, margin_available=margin_available,
                mark_price=mark_price, multiplier=multiplier, leverage=leverage,
            )
            if mres.decision == MarginRuleDecision.BLOCK:
                reasons.extend(mres.reasons)
            elif mres.decision == MarginRuleDecision.WARN:
                warnings.extend(mres.warnings)
            metrics.update(mres.metrics)

            lres = LiquidationRiskRule(
                self.policy.liquidation_critical_pct,
                self.policy.liquidation_warning_pct,
                self.policy.maintenance_margin_pct,
            ).check(order=order, positions=positions, mark_price=mark_price, leverage=leverage)
            if lres.decision == MarginRuleDecision.BLOCK:
                reasons.extend(lres.reasons)
            elif lres.decision == MarginRuleDecision.WARN:
                warnings.extend(lres.warnings)
            for k, v in lres.metrics.items():
                metrics.setdefault(k, v)

        # 6. daily loss
        if self.daily_realized_pnl <= -abs(self.policy.max_daily_loss):
            reasons.append("daily futures loss limit reached")

        decision = FuturesRiskDecision.REJECTED if reasons else FuturesRiskDecision.APPROVED
        return FuturesRiskCheckResult(
            decision=decision, reasons=reasons, warnings=warnings, metrics=metrics
        )
