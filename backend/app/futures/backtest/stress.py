"""Agent / Risk Gate 스트레스 테스트 (Phase 5) — 악조건에서 안전 가드 검증.

기존 가드를 재구현하지 않고 그대로 호출해 정상 동작을 검증한다:
- STALE_PRICE → FuturesRiskManager 가 REJECTED
- HIGH_LEVERAGE → 레버리지 한도 REJECTED
- MARGIN_EXCEEDED → 증거금 한도 REJECTED
- MARKET_CRASH (급락) → 백테스트 stop-loss 가 손실 제한

판정 PASS(가드 보호) / FAIL(보호 실패). **실제 주문 0건.**
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.futures.backtest.engine import BacktestConfig, run_backtest
from app.futures.risk import FuturesRiskDecision, FuturesRiskManager, FuturesRiskPolicy
from app.futures.types import FuturesOrderRequest, FuturesSide


@dataclass
class ScenarioResult:
    name: str
    verdict: str   # PASS / FAIL
    detail: str
    broker_order_sent: bool = False


@dataclass
class StressReport:
    results: list[ScenarioResult] = field(default_factory=list)
    is_order_signal: bool = False
    is_live_authorization: bool = False
    auto_apply_allowed: bool = False
    no_profit_guarantee: bool = True

    def __post_init__(self) -> None:
        if self.is_order_signal or self.is_live_authorization or self.auto_apply_allowed:
            raise ValueError("StressReport safety invariants violated")

    @property
    def passed(self) -> bool:
        return all(r.verdict == "PASS" for r in self.results)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "results": [r.__dict__ for r in self.results],
            "is_order_signal": False, "is_live_authorization": False,
            "auto_apply_allowed": False, "no_profit_guarantee": True,
        }


def _order():
    return FuturesOrderRequest(contract="K", side=FuturesSide.BUY, quantity=1)


def run_stress_test() -> StressReport:
    results: list[ScenarioResult] = []

    # 1. STALE_PRICE
    rm = FuturesRiskManager(FuturesRiskPolicy(max_margin_used=100_000_000))
    res = rm.evaluate_virtual_order(
        order=_order(), positions=[], margin_used=0, margin_available=30_000_000,
        mark_price=350, multiplier=250_000, leverage=5.0,
        price_age_seconds=300, stale_max_age_seconds=60,
    )
    ok = res.decision == FuturesRiskDecision.REJECTED and any("stale" in r for r in res.reasons)
    results.append(ScenarioResult("STALE_PRICE", "PASS" if ok else "FAIL",
                                  "stale price hard-reject" if ok else "guard failed"))

    # 2. HIGH_LEVERAGE
    res = rm.evaluate_virtual_order(
        order=_order(), positions=[], margin_used=0, margin_available=30_000_000,
        mark_price=350, multiplier=250_000, leverage=99.0,
    )
    ok = res.decision == FuturesRiskDecision.REJECTED and any("leverage" in r for r in res.reasons)
    results.append(ScenarioResult("HIGH_LEVERAGE", "PASS" if ok else "FAIL",
                                  "leverage limit reject" if ok else "guard failed"))

    # 3. MARGIN_EXCEEDED
    rm2 = FuturesRiskManager(FuturesRiskPolicy(max_margin_used=1_000_000))
    res = rm2.evaluate_virtual_order(
        order=_order(), positions=[], margin_used=0, margin_available=500_000,
        mark_price=350, multiplier=250_000, leverage=5.0,
    )
    ok = res.decision == FuturesRiskDecision.REJECTED
    results.append(ScenarioResult("MARGIN_EXCEEDED", "PASS" if ok else "FAIL",
                                  "margin limit reject" if ok else "guard failed"))

    # 4. MARKET_CRASH — 급락 시계열에서 stop-loss 가 손실을 제한하는가
    rise = list(range(300, 330))
    crash = list(range(330, 280, -2))  # 급락
    closes = rise + crash
    rep = run_backtest(closes, config=BacktestConfig(stop_loss_pct=1.5, take_profit_pct=3.0))
    # 손실이 발생하더라도 단일 거래 손실이 명목의 큰 비율로 폭주하지 않아야 함
    worst = min(rep.trade_pnls) if rep.trade_pnls else 0
    notional = 300 * 250_000
    ok = worst > -notional * 0.05  # 5% 명목 이내로 제한
    results.append(ScenarioResult("MARKET_CRASH", "PASS" if ok else "FAIL",
                                  f"worst trade {worst} within stop bound" if ok else f"loss runaway {worst}"))

    return StressReport(results=results)
