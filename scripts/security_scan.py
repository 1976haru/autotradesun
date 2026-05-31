#!/usr/bin/env python3
"""read-only 보안 스캐너 — SOURCE(autotrade) 관례 이식 (선물판, 경량).

git 추적 파일을 스캔해 secret / 인증서 / 위험 플래그 활성값을 검출한다.
어떤 파일도 수정하지 않는다. finding 0건이어야 머지 가능.

severity: HIGH(실제 secret/위험 플래그 true) / MEDIUM / LOW / INFO.
False positive 회피: 디렉토리 allowlist + 라인 `# security-scan: ignore` 마커 +
.env.example placeholder(빈값 / your- / <...>).

exit code: 0 = clean, 1 = findings.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 라인 단위 무시 마커
IGNORE_MARKER = "security-scan: ignore"

# 스캔 제외 디렉토리 prefix (테스트 fake / 문서 / 빌드 산출물)
SKIP_PREFIXES = (
    "backend/tests/",
    "docs/",
    "node_modules/",
    "frontend/dist/",
)

# placeholder 로 간주하는 패턴 (실제 secret 아님)
PLACEHOLDER_HINTS = ("your-", "<", "여기에", "example", "placeholder", "xxxx", "0000")

# (name, regex, severity)
PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("openai_api_key", re.compile(r"sk-[A-Za-z0-9]{20,}"), "HIGH"),
    ("anthropic_api_key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "HIGH"),
    ("github_pat", re.compile(r"ghp_[A-Za-z0-9]{30,}"), "HIGH"),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"), "HIGH"),
    ("korean_bank_account", re.compile(r"\b\d{4,6}-\d{2}-\d{6}\b"), "MEDIUM"),
    ("bearer_long_token", re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{30,}"), "MEDIUM"),
    ("enable_futures_live_true", re.compile(r"ENABLE_FUTURES_LIVE_TRADING\s*=\s*true", re.I), "HIGH"),
    ("enable_ai_execution_true", re.compile(r"ENABLE_AI_EXECUTION\s*=\s*true", re.I), "HIGH"),
]


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    return [f for f in out.stdout.splitlines() if f.strip()]


def _looks_like_placeholder(line: str) -> bool:
    low = line.lower()
    return any(h in low for h in PLACEHOLDER_HINTS)


def _mask(s: str) -> str:
    if len(s) <= 8:
        return "****"
    return s[:4] + "..." + s[-4:]


def scan() -> int:
    findings: list[str] = []
    for rel in tracked_files():
        if rel.startswith(SKIP_PREFIXES):
            continue
        if rel.endswith((".png", ".jpg", ".ico", ".woff", ".woff2")):
            continue
        path = REPO_ROOT / rel
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if IGNORE_MARKER in line:
                continue
            for name, pat, sev in PATTERNS:
                m = pat.search(line)
                if not m:
                    continue
                # .env.example placeholder 허용
                if rel.endswith(".env.example") and _looks_like_placeholder(line):
                    continue
                findings.append(f"[{sev}] {name}  {rel}:{i}  {_mask(m.group(0))}")

    if findings:
        print("Security scan: FINDINGS")
        for f in findings:
            print("  " + f)
        return 1
    print("Security scan: clean (0 findings)")
    return 0


if __name__ == "__main__":
    sys.exit(scan())
