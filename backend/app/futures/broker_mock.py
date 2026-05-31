"""MockFuturesBroker (Phase 3) — 가상 선물 체결 + 내부 원장(ledger).

가상 자금/포지션을 보유하고 mark price 기준 즉시 체결을 시뮬레이션한다. 실제
broker live endpoint 를 호출하지 않으며 외부 네트워크 의존이 없다.

**place_order 만이 체결/원장 변경을 수행하는 유일한 코드.** 호출자는 반드시
`FuturesOrderExecutor` 를 거치며 그 앞에 `FuturesRiskManager` 평가가 선행된다.
"""

from __future__ import annotations

import itertools

from app.futures.margin_rules import initial_margin
from app.futures.types import (
    FuturesOrderRequest,
    FuturesOrderResult,
    FuturesOrderStatus,
    FuturesPosition,
    FuturesPositionSide,
    FuturesSide,
)


class MockFuturesBroker:
    is_live = False  # paper-safe broker 식별자

    def __init__(self, initial_cash: int = 50_000_000):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.margin_used = 0
        self.realized_pnl = 0
        self._positions: dict[str, FuturesPosition] = {}
        self._marks: dict[str, int] = {}
        self._mult: dict[str, int] = {}
        self._order_seq = itertools.count(1)

    def set_mark(self, contract: str, price: int) -> None:
        self._marks[contract] = price
        pos = self._positions.get(contract)
        if pos is not None:
            pos.market_price = price

    def mark(self, contract: str) -> int | None:
        return self._marks.get(contract)

    def get_balance(self):
        from app.futures.types import FuturesBalance

        equity = self.cash + self._unrealized_pnl()
        return FuturesBalance(
            cash=self.cash, margin_used=self.margin_used,
            margin_available=max(0, self.cash - self.margin_used), equity=equity,
        )

    def get_positions(self) -> list[FuturesPosition]:
        return [p for p in self._positions.values() if p.quantity != 0]

    def _unrealized_pnl(self) -> int:
        total = 0
        for p in self._positions.values():
            if p.quantity == 0:
                continue
            total += p.unrealized_pnl_points * p.quantity * self._mult.get(p.contract, 1)
        return total

    def place_order(
        self, order: FuturesOrderRequest, *,
        mark_price: int, multiplier: int, leverage: float,
    ) -> FuturesOrderResult:
        self._mult[order.contract] = multiplier
        oid = f"MFB-{next(self._order_seq)}"
        existing = self._positions.get(order.contract)
        qty = order.quantity
        margin_delta = 0

        signed = qty if order.side == FuturesSide.BUY else -qty
        cur_signed = 0
        if existing and existing.quantity:
            cur_signed = (
                existing.quantity if existing.side == FuturesPositionSide.LONG
                else -existing.quantity
            )
        new_signed = cur_signed + signed

        # 청산분(부호 감소) 실현손익
        if cur_signed != 0 and (signed * cur_signed) < 0:
            closing = min(abs(signed), abs(cur_signed))
            entry = existing.entry_price
            pnl_points = (mark_price - entry) if cur_signed > 0 else (entry - mark_price)
            realized = pnl_points * closing * multiplier
            self.realized_pnl += realized
            self.cash += realized
            freed = initial_margin(entry, multiplier, closing, leverage)
            self.margin_used = max(0, self.margin_used - freed)
            margin_delta -= freed

        # 신규/증가분 증거금
        opening = 0
        if new_signed != 0 and (abs(new_signed) > abs(cur_signed) or cur_signed == 0):
            same_dir = (new_signed * cur_signed) > 0
            opening = abs(new_signed) - (abs(cur_signed) if same_dir else 0)
        if opening > 0:
            req = initial_margin(mark_price, multiplier, opening, leverage)
            self.margin_used += req
            margin_delta += req

        # 포지션 갱신 (netting)
        if new_signed == 0:
            self._positions.pop(order.contract, None)
        else:
            side = FuturesPositionSide.LONG if new_signed > 0 else FuturesPositionSide.SHORT
            if cur_signed == 0 or (new_signed * cur_signed) < 0:
                entry_price = mark_price
            elif abs(new_signed) > abs(cur_signed):
                added = abs(new_signed) - abs(cur_signed)
                entry_price = int(
                    (existing.entry_price * abs(cur_signed) + mark_price * added)
                    / abs(new_signed)
                )
            else:
                entry_price = existing.entry_price
            distance = max(1, int(mark_price / leverage)) if leverage > 0 else mark_price
            liq = (
                entry_price - distance if side == FuturesPositionSide.LONG
                else entry_price + distance
            )
            self._positions[order.contract] = FuturesPosition(
                contract=order.contract, side=side, quantity=abs(new_signed),
                entry_price=entry_price, market_price=mark_price,
                margin_used=self.margin_used, liquidation_price=liq,
            )

        return FuturesOrderResult(
            order_id=oid, status=FuturesOrderStatus.FILLED, contract=order.contract,
            side=order.side, quantity=qty, filled_quantity=qty,
            avg_fill_price=mark_price, margin_delta=margin_delta,
            message="virtual fill (MockFuturesBroker)",
        )
