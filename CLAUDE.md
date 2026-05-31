# CLAUDE.md — autotradesun (국내선물 자동매매) 작업 지침

## 프로젝트 정체성

이 프로젝트는 **국내선물(KOSPI200 선물 중심) 단타 자동매매를 위한 리스크
제한형 연구 플랫폼**이다. SOURCE 인 국내주식 자동매매 `autotrade` 의 검증된
안전 아키텍처를 토대로, **모의(SIMULATION) / Paper 자동매매가 "시작 버튼
하나로 끝까지 도는 상태"** 까지 구축하는 것이 1차 범위다. 실거래 수익
자동화가 목적이 아니다.

## 절대 원칙

1. **AI / 코드가 선물 broker 실거래 주문 API 를 직접 호출하는 경로를 만들지 않는다.**
2. **모든 주문은 `FuturesRiskManager → FuturesOrderRouter → FuturesOrderExecutor`
   단일 경로를 거친다.** 새 주문 경로는 반드시 router 를 통과한다.
3. **기본 운용모드는 `SIMULATION` / `PAPER` 이며, 선물 LIVE 는 기본 비활성.**
   `ENABLE_FUTURES_LIVE_TRADING=false` + `FuturesRiskManager.evaluate_order`
   는 항상 `REJECTED`.
4. **API Key / App Secret / 계좌번호 / Anthropic·OpenAI Key 는 frontend 에
   저장하거나 커밋하지 않는다.** backend `.env` (gitignore) 로만 주입.
5. **프론트엔드는 관제·시작/중지 UI 이며, 실제 시세/주문 처리는 backend 에서만.**
6. **advisory 모듈(전략/Council/리포트)은 broker / OrderExecutor / order_router /
   외부 HTTP / AI SDK 를 import 하지 않는다** (정적 grep 가드 테스트로 잠금).
   advisory 산출물은 `is_order_signal=False` 불변.

## 운용모드

| 모드 | 설명 | 본 빌드 |
|---|---|---|
| `SIMULATION` | 합성 시세 + MockFuturesBroker | ✅ 기본값 |
| `PAPER` | 실 시세 + 가상 자금 | ✅ |
| `LIVE_SHADOW` | read-only, 주문 금지 | (게이트 뒤) |
| `LIVE_MANUAL_APPROVAL` | 운영자 승인 | 🛑 비활성 |
| `LIVE_AI_ASSIST` | AI 제안 + 승인 | 🛑 비활성 |
| `LIVE_AI_EXECUTION` | 제한 AI 실행 | 🛑 영구 게이트 뒤 |

## 단일 주문 진입점

모든 선물 주문 경로는 `app/futures/execution/futures_order_router.py::route_futures_order`
를 통과한다:

1. broker 로 시세/잔고/포지션 조회
2. `FuturesRiskManager` 평가 (증거금/레버리지/청산거리/계약수/일일손실)
3. `FuturesOrderAuditLog` 기록 (성공/거부 모두)
4. 분기: REJECTED / NEEDS_APPROVAL / 가상 체결(`FuturesOrderExecutor`)

`FuturesOrderExecutor` 만이 `broker.place_order()` 를 호출하는 유일한 코드다.

## 안전 플래그

| 변수 | 기본 | 효과 |
|---|---|---|
| `DEFAULT_MODE` | `SIMULATION` | 운용모드 분기 |
| `ENABLE_FUTURES_LIVE_TRADING` | `false` | 선물 LIVE 차단 (REJECTED) |
| `ENABLE_AI_EXECUTION` | `false` | AI 자동 실행 차단 |
| `MARKET_DATA_PROVIDER` | `mock` | 시세 소스 (mock/yfinance/kis) |
| `STALE_PRICE_MAX_AGE_SECONDS` | `60` | 오래된 시세 hard-reject |

## 작업 방식

- 큰 기능은 작은 PR/Phase 단위로 쪼갠다.
- 새 기능은 테스트를 함께 추가한다 (backend pytest, frontend vitest).
- 금융 로직은 수익률보다 **손실 방어와 감사 로그** 우선.
- **랜덤 시뮬레이션 결과를 실제 성과로 표현하지 않는다.**
- 선물 LIVE 활성화 PR 은 운영자 명시 옵트인 후에만 머지.

## 코드 구조

```text
backend/app/
├─ core/            # config(안전 플래그), modes
├─ futures/
│  ├─ types.py              # Pydantic 모델 (Quote/Position/Balance/Order...)
│  ├─ contracts/            # 국내선물 계약 레지스트리 + 만기 캘린더
│  ├─ market/               # 선물 시세 어댑터 (mock/yfinance/kis-placeholder)
│  ├─ margin_rules.py       # 레버리지/증거금/청산거리 Rule
│  ├─ risk.py               # FuturesRiskManager (LIVE 항상 REJECTED)
│  ├─ broker_mock.py        # MockFuturesBroker
│  ├─ audit.py              # FuturesOrderAuditLog (in-memory)
│  ├─ execution/            # 단일 주문 진입점 router + executor
│  ├─ auto_loop.py          # FuturesAutoPaperEngine (시작 버튼 백엔드)
│  ├─ strategies/           # FuturesStrategyBase + mock 전략 + Council
│  └─ backtest/             # 메트릭 + 엔진 (Paper 검증)
└─ api/routes_futures.py    # FastAPI endpoints

frontend/src/                # React/Vite 관제 UI (Futures 탭 + 시작 버튼)
scripts/                     # security_scan / 백테스트 / 스모크
docs/                        # 선물 운용/리스크/승격 정책
```

## 변경 시 동기화

다음 변경은 본 문서도 같이 업데이트한다: 새 운용모드 / 안전 플래그 /
`route_futures_order` 가드 체인 / 새 broker·market 어댑터 / 절대 원칙.
