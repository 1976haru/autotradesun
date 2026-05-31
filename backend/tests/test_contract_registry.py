"""Phase 1 — 계약 레지스트리 + 만기 캘린더."""

from datetime import date, datetime

import pytest

from app.futures.contracts.domestic_registry import (
    KST,
    FuturesContractSpec,
    build_registry,
    days_to_expiry,
    get_contract,
    is_contract_expiring_soon,
    list_contracts,
    nearest_quarterly_expiry,
    second_thursday,
    should_rollover,
)

_NOW = datetime(2026, 1, 15, 10, 0, tzinfo=KST)


def test_registry_has_three_products():
    reg = build_registry(now=_NOW)
    assert len(reg) == 3
    assert {s.underlying for s in reg.values()} == {"KOSPI200", "KOSPI200_MINI", "KOSDAQ150"}


def test_contract_spec_values_valid_and_notional():
    reg = build_registry(now=_NOW)
    k200 = next(s for s in reg.values() if s.underlying == "KOSPI200")
    assert k200.multiplier == 250_000
    assert k200.tick_value_krw == 12_500
    assert k200.notional(350.0) == 87_500_000


def test_second_thursday_known_value():
    result = second_thursday(2026, 3)
    assert result == date(2026, 3, 12)
    assert result.weekday() == 3


def test_nearest_quarterly_expiry_is_future_quarter_month():
    exp = nearest_quarterly_expiry(now=_NOW)
    assert exp > _NOW
    assert exp.month in (3, 6, 9, 12)


def test_days_to_expiry_positive_and_negative():
    assert days_to_expiry(datetime(2026, 1, 20, 15, 45, tzinfo=KST), now=_NOW) == 5
    assert days_to_expiry(datetime(2026, 1, 10, tzinfo=KST), now=_NOW) < 0


def test_expiring_soon_and_rollover_advisory():
    spec = FuturesContractSpec(
        code="X_2601", underlying="X", display_name="x",
        multiplier=1000, tick_size_pt=0.05, tick_value_krw=50,
        leverage_max=10.0, expiry=datetime(2026, 1, 18, 15, 45, tzinfo=KST),
    )
    assert is_contract_expiring_soon(spec, now=_NOW, threshold_days=5)
    assert should_rollover(spec, now=_NOW, threshold_days=5)
    assert not is_contract_expiring_soon(spec, now=_NOW, threshold_days=1)


def test_invalid_spec_rejected():
    with pytest.raises(ValueError):
        FuturesContractSpec(
            code="x", underlying="x", display_name="x",
            multiplier=0, tick_size_pt=0.05, tick_value_krw=50,
            leverage_max=10.0, expiry=_NOW,
        )


def test_get_and_list_contract():
    specs = list_contracts(now=_NOW)
    assert len(specs) == 3
    assert get_contract(specs[0].code, now=_NOW) is not None
    assert get_contract("NOPE_9999", now=_NOW) is None
