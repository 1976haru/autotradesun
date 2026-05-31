"""FastAPI 진입점 — autotradesun (국내선물 모의/Paper).

`/health`, `/api/status` 는 안전 플래그 read-only 노출. 선물 라우터는 Phase 3 에서
마운트된다 (routes_futures).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/status")
    def status() -> dict:
        # 안전 플래그 read-only 노출 (secret 0건).
        return {
            "app_name": settings.app_name,
            "default_mode": settings.default_mode.value,
            "enable_futures_live_trading": settings.enable_futures_live_trading,
            "enable_ai_execution": settings.enable_ai_execution,
            "market_data_provider": settings.market_data_provider,
            "is_live_authorization": False,
        }

    # 선물 라우터 (Phase 3+). import 실패해도 health 는 살아있도록 보호.
    try:
        from app.api.routes_futures import router as futures_router

        app.include_router(futures_router)
    except Exception:  # noqa: BLE001 — 라우터 미존재 단계에서도 앱 기동 보장
        pass

    return app


app = create_app()
