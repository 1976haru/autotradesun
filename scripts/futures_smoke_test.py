#!/usr/bin/env python3
"""선물 통합 스모크 테스트 (Phase 8) — read-only, 주문 0건.

health / 안전 플래그 / 계약 레지스트리 / preflight / auto-loop 1 사이클(가상)을
한 번에 점검한다. 실제 broker live 호출 0건.

exit: 0 PASS / 1 FAIL.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def main() -> int:
    from app.core.config import Settings
    from app.core.modes import OperationMode
    from app.futures.audit import FuturesOrderAuditLog
    from app.futures.auto_loop import FuturesAutoPaperEngine
    from app.futures.broker_mock import MockFuturesBroker
    from app.futures.contracts.domestic_registry import list_contracts
    from app.futures.market.futures_market_data import MockFuturesMarketData
    from app.futures.preflight import run_preflight
    from app.futures.risk import FuturesRiskManager, FuturesRiskPolicy
    from app.futures.strategies.council import build_council_decide

    results: list[tuple[str, bool, str]] = []

    s = Settings()
    results.append(("safety_flags",
                    not s.enable_futures_live_trading and not s.enable_ai_execution,
                    "LIVE/AI 비활성"))

    specs = list_contracts()
    results.append(("contracts", len(specs) >= 3, f"{len(specs)} contracts"))

    pre = run_preflight(s)
    results.append(("preflight", pre.ok, f"ok={pre.ok}"))

    # auto-loop 1 사이클 (가상)
    spec = specs[0]
    eng = FuturesAutoPaperEngine(
        mode=OperationMode.SIMULATION,
        broker=MockFuturesBroker(initial_cash=s.futures_paper_initial_cash),
        risk=FuturesRiskManager(FuturesRiskPolicy(max_margin_used=s.futures_max_margin_used)),
        audit=FuturesOrderAuditLog(),
        market_data=MockFuturesMarketData(base_price=spec_base(spec)),
        spec=spec, leverage=5.0, decide=build_council_decide(min_bars=21),
    )
    eng.start()
    for i in range(40):
        eng.tick(now_epoch=float(i))
    st = eng.status()
    results.append(("auto_loop_runs", st.running and st.tick_count == 40,
                    f"ticks={st.tick_count} orders={st.order_count}"))
    results.append(("no_live_authorization", st.is_live_authorization is False
                    if hasattr(st, "is_live_authorization") else True, "paper only"))

    ok = all(r[1] for r in results)
    print("=== 선물 스모크 테스트 ===")
    for name, passed, detail in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}: {detail}")
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


def spec_base(spec) -> int:
    # KOSPI200 류는 ~350pt 근방을 기준으로 합성 시세 생성
    return 350


if __name__ == "__main__":
    sys.exit(main())
