"""백테스트 성과지표 — 순수 함수 (Phase 5).

선물 손익은 *원화 정수* (PnL = 가격차(pt) * 방향 * multiplier - 비용). 숏 손익도
정상 계산된다. 본 모듈은 어떤 주문/실행/외부호출도 하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PerformanceMetrics:
    trades: int
    wins: int
    losses: int
    win_rate: float
    gross_profit: int
    gross_loss: int
    net_pnl: int
    profit_factor: float | None      # None = 손실거래 0 (무한대 대신)
    avg_win: float
    avg_loss: float
    payoff_ratio: float | None
    expectancy: float
    max_drawdown: int
    max_consecutive_losses: int

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def compute_metrics(trade_pnls: list[int]) -> PerformanceMetrics:
    n = len(trade_pnls)
    wins = [p for p in trade_pnls if p > 0]
    losses = [p for p in trade_pnls if p < 0]
    gross_profit = sum(wins)
    gross_loss = -sum(losses)  # 양수
    net = sum(trade_pnls)
    pf = (gross_profit / gross_loss) if gross_loss > 0 else None
    avg_win = (gross_profit / len(wins)) if wins else 0.0
    avg_loss = (gross_loss / len(losses)) if losses else 0.0
    payoff = (avg_win / avg_loss) if avg_loss > 0 else None
    expectancy = (net / n) if n else 0.0

    # max drawdown on cumulative equity curve
    peak = 0
    cum = 0
    mdd = 0
    for p in trade_pnls:
        cum += p
        peak = max(peak, cum)
        mdd = max(mdd, peak - cum)

    # max consecutive losses
    streak = 0
    max_streak = 0
    for p in trade_pnls:
        if p < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    return PerformanceMetrics(
        trades=n, wins=len(wins), losses=len(losses),
        win_rate=(len(wins) / n) if n else 0.0,
        gross_profit=gross_profit, gross_loss=gross_loss, net_pnl=net,
        profit_factor=pf, avg_win=avg_win, avg_loss=avg_loss, payoff_ratio=payoff,
        expectancy=expectancy, max_drawdown=mdd, max_consecutive_losses=max_streak,
    )
