#!/usr/bin/env python3
"""선물 스트레스 테스트 CLI (Phase 5) — 악조건에서 안전 가드 검증.

사용: python scripts/run_futures_stress_test.py [--output reports/futures]
exit: 0 모든 가드 PASS / 1 가드 FAIL. **실제 주문 0건.**
"""

from __future__ import annotations

import argparse
import sys

from _futures_cli_common import write_report

from app.futures.backtest.stress import run_stress_test


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="선물 스트레스 테스트")
    p.add_argument("--output", default="reports/futures")
    args = p.parse_args(argv)

    report = run_stress_test()
    payload = report.to_dict()
    lines = ["# 선물 스트레스 테스트 결과\n",
             "> 안전 가드 동작 검증 — 실제 주문 0건.\n"]
    for r in report.results:
        lines.append(f"- {r.name}: **{r.verdict}** — {r.detail}")
    md = "\n".join(lines) + "\n"
    jp, _ = write_report(args.output, "futures_stress", payload, md)
    print(f"{'OK' if report.passed else 'FAIL'} passed={report.passed} -> {jp}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
