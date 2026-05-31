"""선물 도메인 Pydantic 모델 — SOURCE(autotrade) app/futures/types.py 이식.

KRW 정수 기반 (호가/증거금/손익 모두 정수 원화). 주식 타입과 분리된 별개 계층.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class FuturesSide(StrEnum):
    BUY = "BUY"     # 진입/증가 방향 (LONG 진입 또는 SHORT 청산)
    SELL = "SELL"   # 반대 방향 (SHORT 진입 또는 LONG 청산)


class FuturesPositionSide(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


class FuturesOrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class FuturesOrderStatus(StrEnum):
    RECEIVED = "RECEIVED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


class FuturesQuote(BaseModel):
    contract: str
    price: int
    timestamp: str
    source: str = "mock"
    # epoch seconds (stale 판정용). None 이면 stale 검사 skip.
    epoch: float | None = None


class FuturesPosition(BaseModel):
    contract: str
    side: FuturesPositionSide
    quantity: int          # 계약 수
    entry_price: int
    market_price: int
    margin_used: int
    liquidation_price: int | None = None

    @property
    def unrealized_pnl_points(self) -> int:
        diff = self.market_price - self.entry_price
        return diff if self.side == FuturesPositionSide.LONG else -diff


class FuturesBalance(BaseModel):
    cash: int
    margin_used: int
    margin_available: int
    equity: int
    currency: str = "KRW"


class FuturesOrderRequest(BaseModel):
    contract: str
    side: FuturesSide
    quantity: int = Field(gt=0)        # 계약 수
    order_type: FuturesOrderType = FuturesOrderType.MARKET
    limit_price: int | None = Field(default=None, ge=0)
    # audit / 단일 진입점 carry 필드
    strategy: str | None = None
    trade_reason: str | None = None
    client_order_id: str | None = None


class FuturesOrderResult(BaseModel):
    order_id: str
    status: FuturesOrderStatus
    contract: str
    side: FuturesSide
    quantity: int
    filled_quantity: int = 0
    avg_fill_price: int | None = None
    margin_delta: int = 0
    message: str = ""
