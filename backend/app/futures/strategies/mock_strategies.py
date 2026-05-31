"""Mock 선물 전략 3종 (Phase 4) — 결정적, advisory only.

1. FuturesTrendFollowingStrategy   — SMA 단/장기 교차 → OPEN_LONG/OPEN_SHORT/WATCH
2. FuturesVolatilityBreakoutStrategy— 최근 레인지 돌파 → 진입, 고변동 시 REDUCE_SIZE
3. FuturesMeanReversionStrategy     — 평균 대비 과이탈 → 역추세 진입

모두 만기 임박(expiring_soon) 시 신규 진입을 WATCH 로 강등한다. 무작위 미사용.
"""

from __future__ import annotations

from app.futures.strategies.base import (
    FuturesSignal,
    FuturesSignalAction,
    FuturesStrategyBase,
    FuturesStrategyInput,
)


def _sma(values: list[int], n: int) -> float | None:
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def _downgrade_if_expiring(data: FuturesStrategyInput, action: FuturesSignalAction):
    if data.expiring_soon and action in (
        FuturesSignalAction.OPEN_LONG, FuturesSignalAction.OPEN_SHORT
    ):
        return FuturesSignalAction.WATCH
    return action


class FuturesTrendFollowingStrategy(FuturesStrategyBase):
    name = "trend_following"

    def __init__(self, short: int = 5, long: int = 20):
        self.short = short
        self.long = long

    def evaluate(self, data: FuturesStrategyInput) -> FuturesSignal:
        s = _sma(data.closes, self.short)
        long_ma = _sma(data.closes, self.long)
        if s is None or long_ma is None:
            return self._no_signal(data.contract)
        if s > long_ma:
            action = _downgrade_if_expiring(data, FuturesSignalAction.OPEN_LONG)
            conf = min(90, 50 + int((s - long_ma) / long_ma * 1000))
            return FuturesSignal(action=action, contract=data.contract, confidence=conf,
                                 reason="SMA short>long (uptrend)")
        if s < long_ma:
            action = _downgrade_if_expiring(data, FuturesSignalAction.OPEN_SHORT)
            conf = min(90, 50 + int((long_ma - s) / long_ma * 1000))
            return FuturesSignal(action=action, contract=data.contract, confidence=conf,
                                 reason="SMA short<long (downtrend)")
        return FuturesSignal(action=FuturesSignalAction.WATCH, contract=data.contract,
                             confidence=40, reason="SMA flat")


class FuturesVolatilityBreakoutStrategy(FuturesStrategyBase):
    name = "volatility_breakout"

    def __init__(self, lookback: int = 20, high_vol_pct: float = 5.0):
        self.lookback = lookback
        self.high_vol_pct = high_vol_pct

    def evaluate(self, data: FuturesStrategyInput) -> FuturesSignal:
        if len(data.closes) < self.lookback + 1:
            return self._no_signal(data.contract)
        window = data.closes[-(self.lookback + 1):-1]
        hi, lo = max(window), min(window)
        last = data.closes[-1]
        rng_pct = (hi - lo) / lo * 100 if lo else 0
        if rng_pct >= self.high_vol_pct:
            return FuturesSignal(action=FuturesSignalAction.REDUCE_SIZE, contract=data.contract,
                                 confidence=60, reason=f"high volatility {rng_pct:.1f}%")
        if last > hi:
            action = _downgrade_if_expiring(data, FuturesSignalAction.OPEN_LONG)
            return FuturesSignal(action=action, contract=data.contract, confidence=65,
                                 reason="upper breakout")
        if last < lo:
            action = _downgrade_if_expiring(data, FuturesSignalAction.OPEN_SHORT)
            return FuturesSignal(action=action, contract=data.contract, confidence=65,
                                 reason="lower breakout")
        return FuturesSignal(action=FuturesSignalAction.WATCH, contract=data.contract,
                             confidence=40, reason="inside range")


class FuturesMeanReversionStrategy(FuturesStrategyBase):
    name = "mean_reversion"

    def __init__(self, lookback: int = 20, band_pct: float = 2.0):
        self.lookback = lookback
        self.band_pct = band_pct

    def evaluate(self, data: FuturesStrategyInput) -> FuturesSignal:
        mean = _sma(data.closes, self.lookback)
        if mean is None:
            return self._no_signal(data.contract)
        last = data.closes[-1]
        dev_pct = (last - mean) / mean * 100 if mean else 0
        if dev_pct >= self.band_pct:
            action = (
                FuturesSignalAction.CLOSE_LONG if data.position_side == "LONG"
                else _downgrade_if_expiring(data, FuturesSignalAction.OPEN_SHORT)
            )
            return FuturesSignal(action=action, contract=data.contract, confidence=55,
                                 reason=f"overbought +{dev_pct:.1f}% vs mean")
        if dev_pct <= -self.band_pct:
            action = (
                FuturesSignalAction.CLOSE_SHORT if data.position_side == "SHORT"
                else _downgrade_if_expiring(data, FuturesSignalAction.OPEN_LONG)
            )
            return FuturesSignal(action=action, contract=data.contract, confidence=55,
                                 reason=f"oversold {dev_pct:.1f}% vs mean")
        return FuturesSignal(action=FuturesSignalAction.WATCH, contract=data.contract,
                             confidence=40, reason="near mean")


def default_strategies() -> list[FuturesStrategyBase]:
    return [
        FuturesTrendFollowingStrategy(),
        FuturesVolatilityBreakoutStrategy(),
        FuturesMeanReversionStrategy(),
    ]
