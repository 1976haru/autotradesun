"""FuturesOrderAuditLog (Phase 3) — in-memory append-only 감사 로그.

모든 주문 결정(APPROVED / REJECTED / NEEDS_APPROVAL)을 성공/거부 무관하게 기록.
본 빌드는 in-memory (프로세스 수명) — DB 영속화는 후속.
"""

from __future__ import annotations

import itertools
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class FuturesAuditEntry:
    audit_id: int
    contract: str
    side: str
    quantity: int
    decision: str
    mode: str
    source: str
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    order_id: str | None = None
    filled_quantity: int = 0
    avg_fill_price: int | None = None
    actual_broker_order_sent: bool = False  # 본 빌드 invariant False

    def to_dict(self) -> dict:
        return asdict(self)


class FuturesOrderAuditLog:
    def __init__(self) -> None:
        self._entries: list[FuturesAuditEntry] = []
        self._seq = itertools.count(1)

    def record(
        self, *, contract: str, side: str, quantity: int, decision: str, mode: str,
        source: str, reasons: list[str] | None = None, warnings: list[str] | None = None,
        order_id: str | None = None, filled_quantity: int = 0,
        avg_fill_price: int | None = None,
    ) -> FuturesAuditEntry:
        entry = FuturesAuditEntry(
            audit_id=next(self._seq), contract=contract, side=side, quantity=quantity,
            decision=decision, mode=mode, source=source,
            reasons=list(reasons or []), warnings=list(warnings or []),
            order_id=order_id, filled_quantity=filled_quantity, avg_fill_price=avg_fill_price,
            actual_broker_order_sent=False,
        )
        self._entries.append(entry)
        return entry

    def entries(self, *, limit: int | None = None) -> list[FuturesAuditEntry]:
        items = list(reversed(self._entries))
        return items[:limit] if limit else items

    def count(self) -> int:
        return len(self._entries)
