"""선물 preflight smoke check (Phase 7) — read-only 안전 점검.

빌드/실행 전 안전 플래그·계약 레지스트리·broker paper-safe 여부를 PASS/WARN/FAIL
로 점검한다. 주문을 발생시키지 않으며 broker/route 호출 0건.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import Settings
from app.core.modes import OperationMode, is_paper_safe
from app.futures.broker_mock import MockFuturesBroker
from app.futures.contracts.domestic_registry import list_contracts


@dataclass
class PreflightCheck:
    name: str
    status: str   # PASS / WARN / FAIL
    detail: str


@dataclass
class PreflightReport:
    checks: list[PreflightCheck] = field(default_factory=list)
    is_live_authorization: bool = False
    contains_secret: bool = False

    @property
    def ok(self) -> bool:
        return all(c.status != "FAIL" for c in self.checks)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "checks": [c.__dict__ for c in self.checks],
            "is_live_authorization": False,
            "contains_secret": False,
        }


def run_preflight(settings: Settings | None = None) -> PreflightReport:
    s = settings or Settings()
    checks: list[PreflightCheck] = []

    # 1. LIVE flag off (치명)
    checks.append(PreflightCheck(
        "enable_futures_live_trading",
        "PASS" if not s.enable_futures_live_trading else "FAIL",
        "선물 실거래 비활성" if not s.enable_futures_live_trading else "실거래 활성 — 빌드 차단",
    ))
    # 2. AI execution off
    checks.append(PreflightCheck(
        "enable_ai_execution",
        "PASS" if not s.enable_ai_execution else "FAIL",
        "AI 자동실행 비활성" if not s.enable_ai_execution else "AI 실행 활성 — 차단",
    ))
    # 3. default mode paper-safe
    mode = OperationMode(s.default_mode)
    checks.append(PreflightCheck(
        "default_mode_paper_safe",
        "PASS" if is_paper_safe(mode) else "WARN",
        f"기본 모드 {mode.value}",
    ))
    # 4. 계약 레지스트리
    n = len(list_contracts())
    checks.append(PreflightCheck(
        "contract_registry",
        "PASS" if n >= 1 else "FAIL",
        f"{n} contracts",
    ))
    # 5. broker paper-safe
    broker = MockFuturesBroker()
    checks.append(PreflightCheck(
        "broker_paper_safe",
        "PASS" if not getattr(broker, "is_live", False) else "FAIL",
        "MockFuturesBroker (paper-safe)",
    ))
    return PreflightReport(checks=checks)
