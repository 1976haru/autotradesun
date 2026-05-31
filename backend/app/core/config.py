"""Settings + 안전 플래그 — SOURCE(autotrade) 관례를 선물 빌드로 이식.

절대 원칙: 위험 동작은 env 플래그로 차단하며, 기본값은 모두 안전(차단) 측이다.
어떤 플래그 하나만으로도 선물 실거래가 켜지지 않는다.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.modes import OperationMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "local"
    app_name: str = "autotradesun-backend"

    # ---- 운용모드 ----
    default_mode: OperationMode = OperationMode.SIMULATION

    # ---- 안전 플래그 (모두 기본 차단) ----
    # 선물 실거래 master switch. 본 빌드 범위에서 절대 true 로 두지 않는다.
    enable_futures_live_trading: bool = False
    # AI 자동 실행 (선물에서는 영구 게이트 뒤).
    enable_ai_execution: bool = False

    # ---- 시세 provider ----
    # "mock" 합성 시세 / "yfinance" 지연 시세 / "kis" (placeholder, 본 빌드 미구현)
    market_data_provider: Literal["mock", "yfinance", "kis"] = "mock"

    # ---- CORS / DB ----
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- 선물 리스크 정책 기본값 (운영자 env 조정 가능) ----
    futures_max_contracts: int = 1
    futures_max_margin_used: int = 1_000_000
    futures_max_daily_loss: int = 200_000
    futures_max_leverage: float = 10.0

    # 시세 timestamp 가 N초 초과 oldness 이면 리스크 평가에서 hard-reject.
    stale_price_max_age_seconds: int = 60

    # 자동 루프 tick 간격(초) + 일일 최대 tick (0=무제한).
    futures_auto_tick_interval_seconds: int = 5
    futures_auto_tick_max_per_day: int = 0

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
