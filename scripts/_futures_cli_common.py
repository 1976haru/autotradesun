"""선물 CLI 공통 유틸 — sys.path 설정 + 합성/실 종가 로딩 + 리포트 쓰기."""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def synthetic_closes(n: int = 240, base: int = 320, amp: int = 12, period: int = 40,
                     drift: float = 0.05) -> list[int]:
    """결정적 합성 종가 (sine + 약한 추세). 무작위 미사용 — 재현 가능."""
    out = []
    for i in range(n):
        val = base + drift * i + amp * math.sin(2 * math.pi * i / period)
        out.append(max(1, int(round(val))))
    return out


def load_closes_csv(path: str) -> list[int]:
    """CSV 에서 종가 컬럼 로딩. 헤더에 'close' 가 있으면 그 컬럼, 없으면 마지막 컬럼."""
    closes: list[int] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return closes
    header = rows[0]
    idx = None
    for i, h in enumerate(header):
        if h.strip().lower() in ("close", "종가"):
            idx = i
            break
    start = 0
    if idx is None:
        # 헤더가 숫자면 데이터로 간주, 마지막 컬럼 사용
        try:
            float(header[-1])
            idx = len(header) - 1
        except ValueError:
            idx = len(header) - 1
            start = 1
    else:
        start = 1
    for row in rows[start:]:
        if not row:
            continue
        try:
            closes.append(int(round(float(row[idx]))))
        except (ValueError, IndexError):
            continue
    return closes


def write_report(out_dir: str, name: str, payload: dict, markdown: str) -> tuple[str, str]:
    d = REPO_ROOT / out_dir
    d.mkdir(parents=True, exist_ok=True)
    jpath = d / f"{name}.json"
    mpath = d / f"{name}.md"
    jpath.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    mpath.write_text(markdown, encoding="utf-8")
    return str(jpath), str(mpath)
