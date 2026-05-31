"""Phase 2 — 선물 시세 어댑터."""

import pytest

from app.futures.market.futures_market_data import (
    KisFuturesMarketDataPlaceholder,
    MockFuturesMarketData,
    QuoteStatus,
    YFinanceFuturesMarketData,
    build_market_data,
)


def test_mock_provider_returns_ok_deterministic():
    a = MockFuturesMarketData(base_price=350, amplitude=8)
    b = MockFuturesMarketData(base_price=350, amplitude=8)
    r1 = a.get_quote("KOSPI200_2603", now_epoch=1000.0)
    r2 = b.get_quote("KOSPI200_2603", now_epoch=1000.0)
    assert r1.status == QuoteStatus.OK
    assert r1.quote is not None and r1.quote.price > 0
    assert r1.quote.price == r2.quote.price


def test_mock_provider_price_varies_over_ticks():
    a = MockFuturesMarketData()
    prices = {a.get_quote("X_2603", now_epoch=float(i)).quote.price for i in range(24)}
    assert len(prices) > 1


def test_kis_placeholder_never_calls_network():
    r = KisFuturesMarketDataPlaceholder().get_quote("KOSPI200_2603")
    assert r.status == QuoteStatus.NOT_IMPLEMENTED
    assert r.quote is None
    assert "no live call" in r.reason


def test_yfinance_unavailable_no_silent_mock():
    r = YFinanceFuturesMarketData().get_quote("KOSPI200_2603")
    assert r.status in (QuoteStatus.UNAVAILABLE, QuoteStatus.PROVIDER_ERROR)
    assert r.quote is None and r.reason


def test_factory_known_and_unknown():
    assert isinstance(build_market_data("mock"), MockFuturesMarketData)
    assert isinstance(build_market_data("kis"), KisFuturesMarketDataPlaceholder)
    with pytest.raises(ValueError):
        build_market_data("bogus")


def test_market_data_module_no_http_imports():
    import app.futures.market.futures_market_data as m

    src = open(m.__file__, encoding="utf-8").read()
    assert "import httpx" not in src
    assert "import requests" not in src
    assert "import urllib" not in src
