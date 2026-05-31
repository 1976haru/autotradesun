#!/usr/bin/env python3
"""선물 Walk-forward 검증 CLI (Phase 5).

사용: python scripts/run_futures_walk_forward.py [--input closes.csv] [--synthetic]
      [--train-pct 0.6] [--output reports/futures]
exit: 0 정상 / 2 입력 오류. **결과만으로 실전 전환/자동 적용 0건.**
"""

from __future__ import annotations

import argparse
import sys

from _futures_cli_common import load_closes_csv, synthetic_closes, write_report

from app.futures.backtest.walk_forward import run_walk_forward


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="선물 walk-forward")
    p.add_argument("--input")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--train-pct", type=float, default=0.6)
    p.add_argument("--output", default="reports/futures")
    args = p.parse_args(argv)

    if args.input:
        closes = load_closes_csv(args.input)
    elif args.synthetic:
        closes = synthetic_closes(n=300)
    else:
        print("error: --input 또는 --synthetic 필요", file=sys.stderr)
        return 2
    if len(closes) < 63:
        print("error: 종가 데이터 부족 (walk-forward 는 >=63 필요)", file=sys.stderr)
        return 2

    report = run_walk_forward(closes, train_pct=args.train_pct)
    payload = report.to_dict()
    md = (
        "# 선물 Walk-forward 결과\n\n"
        "> 본 결과는 *시스템 검증 자료*이며 투자 조언/실전 전환 승인/수익 보장이 아닙니다.\n\n"
        f"- reason_code: {report.reason_code}\n"
        f"- train_expectancy: {report.train_expectancy:,.0f}\n"
        f"- test_expectancy: {report.test_expectancy:,.0f}\n"
        f"- retention: {report.retention}\n"
        f"- overfit_suspected: {report.overfit_suspected}\n"
    )
    jp, _ = write_report(args.output, "futures_walk_forward", payload, md)
    print(f"OK reason={report.reason_code} overfit={report.overfit_suspected} -> {jp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
