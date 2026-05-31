"""국내선물 계약 레지스트리 + 만기 캘린더 (Phase 1).

KOSPI200 / 미니 KOSPI200 / 코스닥150 선물의 계약 스펙(multiplier / tick / 틱가치 /
레버리지 한도 / 거래시간)과 만기 규칙을 정의한다.

만기/롤오버 helper(`days_to_expiry` / `is_contract_expiring_soon` / `should_rollover`)
는 **advisory bool/int 만 반환** — 자동 주문 트리거 0건 (CLAUDE.md 절대 원칙).

NOTE: multiplier / tick_value 는 한국거래소 공시 기준 근사값이다. 실거래 활성화
전 거래소 공시값으로 reconcile 해야 한다 (본 빌드는 모의/Paper 범위).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

KST = timezone(timedelta(hours=9))

# 정규장 마감(분기 만기일의 최종거래 마감 시각 근사). SQ 처리는 후속.
_DEFAULT_OPEN = time(9, 0)
_DEFAULT_CLOSE = time(15, 45)


@dataclass(frozen=True)
class FuturesContractSpec:
    """선물 계약 스펙. KRW 정수 기반."""

    code: str               # 예: "KOSPI200_2503" (underlying + YYMM)
    underlying: str         # 예: "KOSPI200"
    display_name: str
    multiplier: int         # 1계약 명목 = mark_price(pt) * multiplier
    tick_size_pt: float     # 호가 단위 (pt)
    tick_value_krw: int     # 1틱 가치 (원) = tick_size_pt * multiplier
    leverage_max: float     # 시장 허용 최대 레버리지
    expiry: datetime        # 최종거래일 마감 시각 (KST)
    currency: str = "KRW"
    market_open_kst: time = _DEFAULT_OPEN
    market_close_kst: time = _DEFAULT_CLOSE

    def __post_init__(self) -> None:
        if self.multiplier <= 0:
            raise ValueError(f"multiplier must be > 0, got {self.multiplier}")
        if self.tick_size_pt <= 0:
            raise ValueError(f"tick_size_pt must be > 0, got {self.tick_size_pt}")
        if self.tick_value_krw <= 0:
            raise ValueError(f"tick_value_krw must be > 0, got {self.tick_value_krw}")
        if self.leverage_max <= 0:
            raise ValueError(f"leverage_max must be > 0, got {self.leverage_max}")

    def notional(self, mark_price_pt: float) -> int:
        """현재가(pt) 기준 1계약 명목금액(원)."""
        return int(mark_price_pt * self.multiplier)


# --------------------------------------------------------------------
# 만기 규칙 — KOSPI200 선물은 3/6/9/12월 둘째 목요일이 만기.
# --------------------------------------------------------------------

_QUARTER_MONTHS = (3, 6, 9, 12)


def second_thursday(year: int, month: int) -> date:
    """해당 월의 둘째 목요일 (KOSPI200 선물 만기일 규칙)."""
    d = date(year, month, 1)
    # weekday(): Mon=0 ... Thu=3
    first_thu_offset = (3 - d.weekday()) % 7
    first_thursday = 1 + first_thu_offset
    return date(year, month, first_thursday + 7)


def nearest_quarterly_expiry(*, now: datetime | None = None) -> datetime:
    """현재 시각 기준 가장 가까운 (미래) 분기물 만기 시각(KST)."""
    cur = (now or datetime.now(KST)).astimezone(KST)
    year = cur.year
    for _ in range(8):  # 최대 2년 탐색
        for m in _QUARTER_MONTHS:
            exp_date = second_thursday(year, m)
            exp_dt = datetime.combine(exp_date, _DEFAULT_CLOSE, tzinfo=KST)
            if exp_dt > cur:
                return exp_dt
        year += 1
    raise RuntimeError("no quarterly expiry found")  # pragma: no cover


def _yymm(dt: datetime) -> str:
    return dt.strftime("%y%m")


# --------------------------------------------------------------------
# 계약 레지스트리 — 근월 분기물 기준 동적 생성.
# --------------------------------------------------------------------

# (underlying, display_name, multiplier, tick_size_pt, tick_value_krw, leverage_max)
_PRODUCTS: tuple[tuple[str, str, int, float, int, float], ...] = (
    # KOSPI200 선물: 1pt = 250,000원, 호가 0.05pt = 12,500원
    ("KOSPI200", "KOSPI200 선물", 250_000, 0.05, 12_500, 10.0),
    # 미니 KOSPI200 선물: 1pt = 50,000원, 호가 0.05pt = 2,500원
    ("KOSPI200_MINI", "미니 KOSPI200 선물", 50_000, 0.05, 2_500, 10.0),
    # 코스닥150 선물: 1pt = 10,000원, 호가 0.10pt = 1,000원
    ("KOSDAQ150", "코스닥150 선물", 10_000, 0.10, 1_000, 10.0),
)


def build_registry(*, now: datetime | None = None) -> dict[str, FuturesContractSpec]:
    """근월 분기물 기준 계약 레지스트리 생성. code -> spec."""
    expiry = nearest_quarterly_expiry(now=now)
    suffix = _yymm(expiry)
    registry: dict[str, FuturesContractSpec] = {}
    for underlying, name, mult, tick, tickval, lev in _PRODUCTS:
        code = f"{underlying}_{suffix}"
        registry[code] = FuturesContractSpec(
            code=code,
            underlying=underlying,
            display_name=f"{name} ({suffix})",
            multiplier=mult,
            tick_size_pt=tick,
            tick_value_krw=tickval,
            leverage_max=lev,
            expiry=expiry,
        )
    return registry


def get_contract(code: str, *, now: datetime | None = None) -> FuturesContractSpec | None:
    return build_registry(now=now).get(code)


def list_contracts(*, now: datetime | None = None) -> list[FuturesContractSpec]:
    return list(build_registry(now=now).values())


# --------------------------------------------------------------------
# 만기 / 롤오버 advisory helpers (자동 주문 트리거 0건)
# --------------------------------------------------------------------


def _to_aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=KST) if dt.tzinfo is None else dt.astimezone(KST)


def days_to_expiry(expiry: datetime, *, now: datetime | None = None) -> int:
    """만기까지 남은 calendar day 근사 (영업일/휴장일 미반영)."""
    expiry = _to_aware(expiry)
    cur = _to_aware(now or datetime.now(KST))
    seconds = (expiry - cur).total_seconds()
    if seconds >= 0:
        return int(seconds // 86400)
    return -(int((-seconds) // 86400) + (1 if (-seconds) % 86400 else 0))


def is_contract_expiring_soon(
    spec: FuturesContractSpec, *, now: datetime | None = None, threshold_days: int = 5
) -> bool:
    """만기 ≤ threshold_days 이면 True (신규 진입 회피 advisory)."""
    if threshold_days < 0:
        raise ValueError(f"threshold_days must be >= 0, got {threshold_days}")
    return days_to_expiry(spec.expiry, now=now) <= threshold_days


def should_rollover(
    spec: FuturesContractSpec, *, now: datetime | None = None, threshold_days: int = 5
) -> bool:
    """근월물 → 차월물 롤오버 권고 여부 (advisory only — 주문 트리거 0건)."""
    return is_contract_expiring_soon(spec, now=now, threshold_days=threshold_days)
