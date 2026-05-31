"""선물 시세 어댑터 (Phase 2).

`MARKET_DATA_PROVIDER` 에 따라 시세를 제공한다:
- "mock"     — 결정적 합성 시세 (tick 인덱스 기반, 무작위 아님 → 재현 가능)
- "yfinance" — 지연 시세 (미설치/네트워크 실패 시 명시적 사유, mock 으로 swap 안 함)
- "kis"      — KIS 선물 실시세 *placeholder*. 공식 endpoint 확인 전 실제 호출 0건
               (httpx/requests import 0건). 항상 NOT_IMPLEMENTED 사유 반환.

데이터 부족/오류 시 조용히 멈추지 않고 명시 사유 코드를 담은 결과를 반환한다.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from enum import StrEnum

from app.futures.types import FuturesQuote


class QuoteStatus(StrEnum):
    OK = "OK"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


@dataclass
class QuoteResult:
    status: QuoteStatus
    quote: FuturesQuote | None = None
    reason: str = ""


class MockFuturesMarketData:
    """결정적 합성 시세. random 미사용 — tick 인덱스 기반 sine wave."""

    def __init__(self, base_price: int = 350, amplitude: int = 8, period: int = 24):
        self.base_price = base_price
        self.amplitude = amplitude
        self.period = max(2, period)
        self._tick = 0

    def _price_at(self, tick: int, contract: str) -> int:
        phase = sum(ord(c) for c in contract) % self.period
        val = self.base_price + self.amplitude * math.sin(
            2 * math.pi * (tick + phase) / self.period
        )
        return max(1, int(round(val)))

    def get_quote(self, contract: str, *, now_epoch: float | None = None) -> QuoteResult:
        price = self._price_at(self._tick, contract)
        self._tick += 1
        epoch = now_epoch if now_epoch is not None else time.time()
        q = FuturesQuote(
            contract=contract, price=price, timestamp=str(int(epoch)),
            source="mock", epoch=epoch,
        )
        return QuoteResult(status=QuoteStatus.OK, quote=q)


class YFinanceFuturesMarketData:
    """yfinance 기반 지연 시세 (옵션, lazy import). 실패는 명시 사유로 반환."""

    def __init__(self, symbol_map: dict[str, str] | None = None):
        self.symbol_map = symbol_map or {}

    def get_quote(self, contract: str, *, now_epoch: float | None = None) -> QuoteResult:
        try:
            import yfinance  # noqa: F401
        except ImportError:
            return QuoteResult(
                status=QuoteStatus.UNAVAILABLE,
                reason="yfinance not installed (optional dependency)",
            )
        yahoo = self.symbol_map.get(contract)
        if not yahoo:
            return QuoteResult(
                status=QuoteStatus.UNAVAILABLE,
                reason=f"no yahoo symbol mapping for contract '{contract}'",
            )
        try:  # pragma: no cover — network path
            import yfinance as yf

            data = yf.Ticker(yahoo).fast_info
            price = getattr(data, "last_price", None)
            if price is None:
                return QuoteResult(
                    status=QuoteStatus.PROVIDER_ERROR, reason="empty yfinance response"
                )
            epoch = now_epoch if now_epoch is not None else time.time()
            q = FuturesQuote(
                contract=contract, price=int(round(price)),
                timestamp=str(int(epoch)), source="yfinance", epoch=epoch,
            )
            return QuoteResult(status=QuoteStatus.OK, quote=q)
        except Exception as e:  # noqa: BLE001
            return QuoteResult(status=QuoteStatus.PROVIDER_ERROR, reason=str(e)[:120])


class KisFuturesMarketDataPlaceholder:
    """KIS 선물 실시세 placeholder — 실제 호출 0건 (httpx/requests import 없음)."""

    def get_quote(self, contract: str, *, now_epoch: float | None = None) -> QuoteResult:
        return QuoteResult(
            status=QuoteStatus.NOT_IMPLEMENTED,
            reason="KIS futures quote endpoint not confirmed; no live call in this build",
        )


def build_market_data(provider: str):
    if provider == "mock":
        return MockFuturesMarketData()
    if provider == "yfinance":
        return YFinanceFuturesMarketData()
    if provider == "kis":
        return KisFuturesMarketDataPlaceholder()
    raise ValueError(f"unknown market data provider: {provider!r}")
