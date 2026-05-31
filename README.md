# autotradesun — 국내선물 모의/Paper 자동매매 연구 플랫폼

국내주식 자동매매 `autotrade` 의 검증된 안전 아키텍처를 토대로 만든 **국내선물
(KOSPI200 선물 중심) 모의/Paper 자동매매** 플랫폼이다. **"국내선물 모의 자동매매
시작" 버튼 하나로** 시세 수신 → 전략/Council 판단 → `FuturesRiskManager` 평가
(증거금/레버리지/청산거리) → 가상 체결(`MockFuturesBroker`) → 감사 로그 → 포지션/
손익 대시보드 갱신까지 **broker 실거래 호출 0건으로** 끝까지 동작한다.

> ⚠️ 본 플랫폼은 **모의/Paper 연구·검증용**이다. 선물 **실거래(LIVE)는 비활성**
> 이며 시작 버튼으로 켜지지 않는다. "수익 보장" / "자동 실전 전환" 은 없다.

## 안전 경계 (절대 변경 금지)

- `ENABLE_FUTURES_LIVE_TRADING=false` 기본값 — `FuturesRiskManager.evaluate_order`
  는 LIVE 분기에서 **항상 REJECTED**.
- 모든 주문은 단일 진입점 `route_futures_order → FuturesRiskManager →
  FuturesOrderExecutor` 를 거친다. `FuturesOrderExecutor` 만이 broker 를 호출.
- 실거래 활성화는 [`docs/futures_promotion_policy.md`](docs/futures_promotion_policy.md)
  의 다단계 게이트 뒤에 있으며 본 빌드에 포함되지 않는다.
- API Key / Secret / 계좌번호는 frontend·git 에 저장 금지 — backend `.env`(gitignore)만.

## 실행 방법

### 1) 백엔드

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # 안전 기본값 유지 권장
uvicorn app.main:app --reload --port 8000
```

확인: http://localhost:8000/health , http://localhost:8000/api/status

### 2) 프론트엔드

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

## 시작 버튼 사용법

1. 백엔드와 프론트엔드를 실행한다.
2. 브라우저에서 http://localhost:5173 접속 → **Futures 화면**.
3. **"국내선물 모의 자동매매 시작"** 버튼 클릭.
4. 상태가 `RUNNING` 으로 바뀌고, tick/주문(가상)/거부 카운트·포지션·감사 로그가
   갱신된다. "실거래(LIVE)" 버튼은 항상 비활성이다.
5. "중지" 버튼으로 멈춘다.

API 로 직접 확인: `POST /api/futures/auto/start`, `GET /api/futures/auto/status`,
`GET /api/futures/positions`, `GET /api/futures/audit`, `GET /api/futures/preflight`.

## 검증

```bash
# backend
cd backend && ruff check app tests && pytest -q
# frontend
cd frontend && npm run lint && npm test && npm run build
# 보안 스캔 + 스모크
python scripts/security_scan.py
python scripts/futures_smoke_test.py
```

## 백테스트 / Walk-forward / Stress (Paper 검증)

```bash
python scripts/run_futures_backtest.py --synthetic
python scripts/run_futures_walk_forward.py --synthetic
python scripts/run_futures_stress_test.py
```

산출물은 `reports/` (gitignore) 에 JSON+MD 로 저장된다. **결과만으로 실전 전환/
자동 적용 0건.**

## 문서

- [작업 지침 (CLAUDE.md)](CLAUDE.md)
- [선물 승격 정책](docs/futures_promotion_policy.md)
