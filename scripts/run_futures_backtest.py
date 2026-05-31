#!/usr/bin/env python3
"""선물 백테스트 CLI (Phase 5).

사용: python scripts/run_futures_backtest.py [--input closes.csv] [--synthetic]
      [--multiplier 250000] [--output reports/futures]

exit: 0 정상 / 2 입력 오류. **결과만으로 실전 전환/자동 적용 0건.**
"""

from __future__ import annotations

import argparse
import sys

from _futures_cli_common import load_closes_csv, synthetic_closes, write_report

from app.futures.backtest.engine import BacktestConfig, run_backtest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="선물 백테스트")
    p.add_argument("--input", help="종가 CSV (close 컬럼)")
    p.add_argument("--synthetic", action="store_true", help="합성 종가 사용")
    p.add_argument("--multiplier", type=int, default=250_000)
    p.add_argument("--output", default="reports/futures")
    args = p.parse_args(argv)

    if args.input:
        closes = load_closes_csv(args.input)
    elif args.synthetic:
        closes = synthetic_closes()
    else:
        print("error: --input 또는 --synthetic 필요", file=sys.stderr)
        return 2
    if len(closes) < 30:
        print("error: 종가 데이터 부족 (>=30 필요)", file=sys.stderr)
        return 2

    report = run_backtest(closes, config=BacktestConfig(multiplier=args.multiplier))
    payload = report.to_dict()
    m = report.metrics
    md = (
        "# 선물 백테스트 결과\n\n"
        "> 본 결과는 *시스템 검증 자료*이며 투자 조언/실전 전환 승인/수익 보장이 아닙니다.\n\n"
        f"- bars: {report.bars}\n- trades: {m.trades}\n- win_rate: {m.win_rate:.2%}\n"
        f"- net_pnl: {m.net_pnl:,} KRW\n- profit_factor: {m.profit_factor}\n"
        f"- expectancy: {m.expectancy:,.0f}\n- max_drawdown: {m.max_drawdown:,}\n"
        f"- max_consecutive_losses: {m.max_consecutive_losses}\n"
    )
    jp, mp = write_report(args.output, "futures_backtest", payload, md)
    print(f"OK trades={m.trades} net_pnl={m.net_pnl} -> {jp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
