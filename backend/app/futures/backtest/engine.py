"""선물 백테스트 엔진 (Phase 5) — Council 신호를 과거 종가에 적용.

양방향(롱/숏) 단일 포지션을 시뮬레이션한다. 손익은 multiplier 반영, 숏 손익도
정상 계산. exit: 신호 반전 / stop·target % / 데이터 끝(강제 청산). 비용(수수료+
슬리피지 틱) 반영. **백테스트 결과만으로 실전 전환/자동 적용 0건.**
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.futures.backtest.metrics import PerformanceMetrics, compute_metrics
from app.futures.strategies.base import FuturesSignalAction, FuturesStrategyInput
from app.futures.strategies.council import run_council


@dataclass
class BacktestConfig:
    multiplier: int = 250_000
    tick_value_krw: int = 12_500
    commission_krw: int = 1_000        # 1회 체결당 수수료(왕복은 진입/청산 각 1회)
    slippage_ticks: int = 1            # 체결당 슬리피지 (틱)
    stop_loss_pct: float = 1.5
    take_profit_pct: float = 3.0
    min_bars: int = 21


@dataclass
class BacktestReport:
    config: dict
    metrics: PerformanceMetrics
    bars: int
    trade_pnls: list[int] = field(default_factory=list)
    # 불변 안전 플래그
    is_order_signal: bool = False
    is_live_authorization: bool = False
    auto_apply_allowed: bool = False
    no_profit_guarantee: bool = True

    def __post_init__(self) -> None:
        if self.is_order_signal or self.is_live_authorization or self.auto_apply_allowed:
            raise ValueError("BacktestReport safety invariants violated")
        if not self.no_profit_guarantee:
            raise ValueError("no_profit_guarantee must be True")

    def to_dict(self) -> dict:
        return {
            "config": self.config, "bars": self.bars,
            "metrics": self.metrics.to_dict(), "trade_count": len(self.trade_pnls),
            "is_order_signal": False, "is_live_authorization": False,
            "auto_apply_allowed": False, "no_profit_guarantee": True,
        }


class _Pos:
    __slots__ = ("side", "entry")

    def __init__(self, side: str, entry: int):
        self.side = side  # "LONG"/"SHORT"
        self.entry = entry


def run_backtest(closes: list[int], contract: str = "BT", config: BacktestConfig | None = None) -> BacktestReport:
    cfg = config or BacktestConfig()
    cost_per_fill = cfg.commission_krw + cfg.slippage_ticks * cfg.tick_value_krw
    pos: _Pos | None = None
    trade_pnls: list[int] = []

    def _close(exit_price: int) -> None:
        nonlocal pos
        if pos is None:
            return
        diff = (exit_price - pos.entry) if pos.side == "LONG" else (pos.entry - exit_price)
        pnl = diff * cfg.multiplier - 2 * cost_per_fill  # 진입+청산 비용
        trade_pnls.append(pnl)
        pos = None

    for i in range(len(closes)):
        price = closes[i]
        hist = closes[: i + 1]

        # exit checks (stop/target) on open position
        if pos is not None:
            move_pct = (price - pos.entry) / pos.entry * 100
            signed = move_pct if pos.side == "LONG" else -move_pct
            if signed <= -cfg.stop_loss_pct or signed >= cfg.take_profit_pct:
                _close(price)

        if len(hist) < cfg.min_bars:
            continue

        decision = run_council(
            FuturesStrategyInput(
                contract=contract, closes=hist,
                position_side=pos.side if pos else None,
            )
        )
        a = decision.final_action
        if pos is None:
            if a == FuturesSignalAction.OPEN_LONG:
                pos = _Pos("LONG", price)
            elif a == FuturesSignalAction.OPEN_SHORT:
                pos = _Pos("SHORT", price)
        else:
            # 반대/청산 신호면 청산
            if pos.side == "LONG" and a in (
                FuturesSignalAction.CLOSE_LONG, FuturesSignalAction.OPEN_SHORT
            ):
                _close(price)
            elif pos.side == "SHORT" and a in (
                FuturesSignalAction.CLOSE_SHORT, FuturesSignalAction.OPEN_LONG
            ):
                _close(price)

    if pos is not None and closes:
        _close(closes[-1])  # 데이터 끝 강제 청산

    return BacktestReport(
        config=cfg.__dict__.copy(), metrics=compute_metrics(trade_pnls),
        bars=len(closes), trade_pnls=trade_pnls,
    )
