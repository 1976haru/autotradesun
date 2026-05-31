"""Walk-forward 과최적화 검증 (Phase 5) — 시간 순서 분할 train/test.

과거 종가를 시간 순서로 분할(미래 데이터를 train 에 섞지 않음)하고 각 구간을
백테스트해 train 대비 test 성과 유지율(retention)과 overfit 의심을 산출한다.
**검증 결과만으로 실전 전환/자동 적용 0건.**
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.futures.backtest.engine import BacktestConfig, run_backtest


@dataclass
class WalkForwardReport:
    segments: int
    train_expectancy: float
    test_expectancy: float
    retention: float | None        # test_exp / train_exp (train>0 일 때만)
    overfit_suspected: bool
    per_segment: list[dict] = field(default_factory=list)
    reason_code: str = "WALK_FORWARD_OK"
    is_order_signal: bool = False
    is_live_authorization: bool = False
    auto_apply_allowed: bool = False
    no_profit_guarantee: bool = True

    def __post_init__(self) -> None:
        if self.is_order_signal or self.is_live_authorization or self.auto_apply_allowed:
            raise ValueError("WalkForwardReport safety invariants violated")

    def to_dict(self) -> dict:
        return {
            "segments": self.segments, "train_expectancy": self.train_expectancy,
            "test_expectancy": self.test_expectancy, "retention": self.retention,
            "overfit_suspected": self.overfit_suspected, "reason_code": self.reason_code,
            "per_segment": self.per_segment,
            "is_order_signal": False, "is_live_authorization": False,
            "auto_apply_allowed": False, "no_profit_guarantee": True,
        }


def run_walk_forward(
    closes: list[int], *, train_pct: float = 0.6, config: BacktestConfig | None = None,
    retention_threshold: float = 0.5,
) -> WalkForwardReport:
    cfg = config or BacktestConfig()
    n = len(closes)
    if n < cfg.min_bars * 3:
        return WalkForwardReport(
            segments=0, train_expectancy=0.0, test_expectancy=0.0, retention=None,
            overfit_suspected=False, reason_code="WALK_FORWARD_INSUFFICIENT_DATA",
        )
    split = int(n * train_pct)
    train_closes = closes[:split]
    test_closes = closes[split:]

    train = run_backtest(train_closes, config=cfg)
    test = run_backtest(test_closes, config=cfg)
    train_exp = train.metrics.expectancy
    test_exp = test.metrics.expectancy

    if train_exp > 0:
        retention = test_exp / train_exp
    else:
        retention = None
    overfit = bool(train_exp > 0 and (test_exp <= 0 or (retention is not None and retention < retention_threshold)))
    reason = "WALK_FORWARD_OVERFIT_SUSPECTED" if overfit else "WALK_FORWARD_OK"

    per = [
        {"segment": "train", **train.metrics.to_dict()},
        {"segment": "test", **test.metrics.to_dict()},
    ]
    return WalkForwardReport(
        segments=2, train_expectancy=train_exp, test_expectancy=test_exp,
        retention=retention, overfit_suspected=overfit, per_segment=per, reason_code=reason,
    )
