"""선물 모의/Paper 자동매매 API (Phase 3) — 시작 버튼 백엔드.

POST /api/futures/auto/start | stop | tick, GET /api/futures/auto/status,
GET /api/futures/positions | audit | contracts.

엔진은 프로세스 단일 인스턴스(in-memory). decide 콜백은 Phase 4 의 선물 Council
이 있으면 그것을, 없으면 단순 내장 전략을 사용한다.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.modes import OperationMode
from app.futures.audit import FuturesOrderAuditLog
from app.futures.auto_loop import FuturesAutoPaperEngine
from app.futures.broker_mock import MockFuturesBroker
from app.futures.contracts.domestic_registry import list_contracts
from app.futures.market.futures_market_data import build_market_data
from app.futures.risk import FuturesRiskManager, FuturesRiskPolicy
from app.futures.types import FuturesOrderRequest, FuturesSide

router = APIRouter(prefix="/api/futures", tags=["futures"])


def _build_decide():
    """Phase 4 Council 이 있으면 사용, 없으면 단순 내장 전략(flat→long)."""
    try:
        from app.futures.strategies.council import build_council_decide

        return build_council_decide()
    except Exception:  # noqa: BLE001 — Phase 4 미존재 시 fallback
        def _simple(contract, quote, positions):
            if not positions:
                return FuturesOrderRequest(
                    contract=contract, side=FuturesSide.BUY, quantity=1, strategy="builtin"
                )
            return None

        return _simple


class _EngineState:
    def __init__(self) -> None:
        self.engine: FuturesAutoPaperEngine | None = None

    def get(self) -> FuturesAutoPaperEngine:
        if self.engine is None:
            self.engine = self._build()
        return self.engine

    def _build(self) -> FuturesAutoPaperEngine:
        s = get_settings()
        spec = list_contracts()[0]  # 근월 KOSPI200
        policy = FuturesRiskPolicy(
            max_contracts=s.futures_max_contracts,
            max_margin_used=s.futures_max_margin_used,
            max_daily_loss=s.futures_max_daily_loss,
            max_leverage=s.futures_max_leverage,
        )
        return FuturesAutoPaperEngine(
            mode=OperationMode(s.default_mode),
            broker=MockFuturesBroker(),
            risk=FuturesRiskManager(policy),
            audit=FuturesOrderAuditLog(),
            market_data=build_market_data(s.market_data_provider),
            spec=spec,
            leverage=min(5.0, s.futures_max_leverage),
            decide=_build_decide(),
            stale_max_age_seconds=s.stale_price_max_age_seconds,
        )


_state = _EngineState()


@router.post("/auto/start")
def auto_start() -> dict:
    eng = _state.get()
    st = eng.start()
    if st.running:
        eng.tick()  # 시작 즉시 1 tick — 버튼 누름이 곧 동작으로 보이도록
    return _status_dict(eng)


@router.post("/auto/stop")
def auto_stop() -> dict:
    eng = _state.get()
    eng.stop()
    return _status_dict(eng)


@router.post("/auto/tick")
def auto_tick() -> dict:
    eng = _state.get()
    eng.tick()
    return _status_dict(eng)


@router.get("/auto/status")
def auto_status() -> dict:
    return _status_dict(_state.get())


@router.get("/positions")
def positions() -> dict:
    b = _state.get().broker
    return {
        "balance": b.get_balance().model_dump(),
        "positions": [p.model_dump() for p in b.get_positions()],
        "realized_pnl": b.realized_pnl,
    }


@router.get("/audit")
def audit(limit: int = 50) -> dict:
    log = _state.get().audit
    return {"count": log.count(), "entries": [e.to_dict() for e in log.entries(limit=limit)]}


@router.get("/contracts")
def contracts() -> dict:
    return {
        "contracts": [
            {
                "code": s.code, "underlying": s.underlying, "display_name": s.display_name,
                "multiplier": s.multiplier, "tick_value_krw": s.tick_value_krw,
                "leverage_max": s.leverage_max, "expiry": s.expiry.isoformat(),
            }
            for s in list_contracts()
        ]
    }


def _status_dict(eng: FuturesAutoPaperEngine) -> dict:
    st = eng.status()
    return {
        "running": st.running, "mode": st.mode, "contract": st.contract,
        "tick_count": st.tick_count, "order_count": st.order_count,
        "reject_count": st.reject_count, "last_price": st.last_price,
        "last_reasons": st.last_reasons, "blocked_reason": st.blocked_reason,
        "is_live_authorization": False,
    }
