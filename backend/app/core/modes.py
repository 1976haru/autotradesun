"""운용모드 정의 — 주식 SOURCE(autotrade)의 OperationMode 관례를 선물에 맞게 이식.

선물 1차 빌드 범위는 SIMULATION / PAPER 까지다. LIVE_* 모드는 enum 으로 존재하되
`ENABLE_FUTURES_LIVE_TRADING=false` 기본값 + `FuturesRiskManager` LIVE 분기 항상
REJECTED 로 코드 단에서 차단된다 (docs/futures_promotion_policy.md).
"""

from __future__ import annotations

from enum import StrEnum


class OperationMode(StrEnum):
    SIMULATION = "SIMULATION"            # 합성 시세 + MockFuturesBroker (기본값)
    PAPER = "PAPER"                      # 실 시세 + 가상 자금 (KIS 모의 등)
    LIVE_SHADOW = "LIVE_SHADOW"          # read-only, 주문 금지
    LIVE_MANUAL_APPROVAL = "LIVE_MANUAL_APPROVAL"   # (게이트 뒤, 본 빌드 비활성)
    LIVE_AI_ASSIST = "LIVE_AI_ASSIST"               # (게이트 뒤, 본 빌드 비활성)
    LIVE_AI_EXECUTION = "LIVE_AI_EXECUTION"         # (영구 게이트 뒤, 본 빌드 비활성)


# 본 빌드에서 가상 체결이 허용되는 모드 — broker live 호출 0건 보장 경계.
PAPER_SAFE_MODES: frozenset[OperationMode] = frozenset(
    {OperationMode.SIMULATION, OperationMode.PAPER}
)


def is_paper_safe(mode: OperationMode) -> bool:
    """가상 자동매매 루프가 동작 가능한 모드인지."""
    return mode in PAPER_SAFE_MODES


def is_live_mode(mode: OperationMode) -> bool:
    """실거래 의도가 있는 LIVE_* 모드인지 (본 빌드에서 모두 차단됨)."""
    return mode in {
        OperationMode.LIVE_MANUAL_APPROVAL,
        OperationMode.LIVE_AI_ASSIST,
        OperationMode.LIVE_AI_EXECUTION,
    }
