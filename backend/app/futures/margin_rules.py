"""선물 증거금 / 레버리지 / 청산거리 Rule (Phase 3).

`FuturesRiskManager` 가 위임 호출하는 명시적 Rule 3종. 위험 *계산* 전용 —
어떤 Rule 도 broker 호출이나 강제청산 주문을 트리거하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.futures.types import FuturesOrderRequest, FuturesPosition, FuturesSide


class MarginRuleDecision(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"


@dataclass
class RuleResult:
    decision: MarginRuleDecision
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def initial_margin(mark_price: int, multiplier: int, quantity: int, leverage: float) -> int:
    """1계약 명목 = mark_price * multiplier; 초기증거금 = 명목 / leverage."""
    notional = mark_price * multiplier * quantity
    return int(notional / leverage) if leverage > 0 else notional


@dataclass
class LeverageLimitRule:
    policy_max_leverage: float
    contract_leverage_max: float | None = None

    def effective_max(self) -> float:
        if self.contract_leverage_max is None:
            return self.policy_max_leverage
        return min(self.policy_max_leverage, self.contract_leverage_max)

    def check(self, leverage: float) -> RuleResult:
        cap = self.effective_max()
        res = RuleResult(
            decision=MarginRuleDecision.PASS,
            metrics={"leverage": leverage, "max_leverage": cap},
        )
        if leverage <= 0:
            res.decision = MarginRuleDecision.BLOCK
            res.reasons.append("leverage must be positive")
        elif leverage > cap:
            res.decision = MarginRuleDecision.BLOCK
            res.reasons.append(f"leverage {leverage} exceeds max_leverage {cap}")
        return res


@dataclass
class FuturesMarginRule:
    max_margin_used: int
    maintenance_margin_pct: float = 10.0

    def check(
        self, *, order: FuturesOrderRequest, margin_used: int, margin_available: int,
        mark_price: int, multiplier: int, leverage: float,
    ) -> RuleResult:
        req = initial_margin(mark_price, multiplier, order.quantity, leverage)
        res = RuleResult(decision=MarginRuleDecision.PASS)
        res.metrics["initial_margin_required"] = req
        res.metrics["margin_used_after"] = margin_used + req
        if req > margin_available:
            res.decision = MarginRuleDecision.BLOCK
            res.reasons.append(
                f"initial margin {req} exceeds margin_available {margin_available}"
            )
        elif margin_used + req > self.max_margin_used:
            res.decision = MarginRuleDecision.BLOCK
            res.reasons.append(
                f"margin_used {margin_used + req} exceeds max_margin_used {self.max_margin_used}"
            )
        else:
            maint = int(
                mark_price * multiplier * order.quantity * self.maintenance_margin_pct / 100
            )
            res.metrics["maintenance_margin"] = maint
            if margin_available - req < maint:
                res.decision = MarginRuleDecision.WARN
                res.warnings.append("low maintenance margin buffer after order")
        return res


@dataclass
class LiquidationRiskRule:
    """청산거리(%) 근사. distance = (100/leverage) - maintenance_margin_pct."""

    critical_pct: float = 3.0
    warning_pct: float = 7.0
    maintenance_margin_pct: float = 10.0

    def check(
        self, *, order: FuturesOrderRequest, positions: list[FuturesPosition],
        mark_price: int, leverage: float,
    ) -> RuleResult:
        res = RuleResult(decision=MarginRuleDecision.PASS)
        if leverage <= 0 or mark_price <= 0:
            return res
        distance_pct = max(0.0, (100.0 / leverage) - self.maintenance_margin_pct)
        liq_offset = mark_price * distance_pct / 100.0
        side_long = order.side == FuturesSide.BUY
        liq_price = int(mark_price - liq_offset) if side_long else int(mark_price + liq_offset)
        res.metrics["liquidation_distance_pct"] = round(distance_pct, 3)
        res.metrics["liquidation_price"] = liq_price
        if distance_pct <= self.critical_pct:
            res.decision = MarginRuleDecision.BLOCK
            res.reasons.append(
                f"liquidation distance {distance_pct:.2f}% <= critical {self.critical_pct}%"
            )
        elif distance_pct <= self.warning_pct:
            res.decision = MarginRuleDecision.WARN
            res.warnings.append(
                f"liquidation distance {distance_pct:.2f}% within warning {self.warning_pct}%"
            )
        return res
