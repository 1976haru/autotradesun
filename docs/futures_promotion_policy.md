# 선물 승격 정책 (futures_promotion_policy)

선물 기능은 자동매매 전체에서 **가장 마지막** 단계다. 레버리지 + 강제청산 +
만기 + (24시간 거래) 로 위험이 한 등급 높기 때문에, 주식 SOURCE 의 다단계
게이트를 그대로 따르되 그 **뒤에** 둔다. 본 1차 빌드 범위는 **SIMULATION /
PAPER 까지**이며, 아래 LIVE 단계는 *코드로 차단*되어 있고 본 PR 에서 활성화하지
않는다.

## 7단계 승격

| 단계 | 설명 | 본 빌드 |
|---|---|---|
| `FUTURES_DISABLED` | 선물 비활성 | — |
| `SIMULATION` | 합성 시세 + MockFuturesBroker | ✅ 동작 |
| `PAPER` | 실 시세(준비) + 가상 자금 | ✅ 구조 |
| `LIVE_SHADOW` | read-only, 주문 금지 | 🛑 게이트 |
| `LIVE_MANUAL_APPROVAL` | 운영자 명시 승인 후 주문 | 🛑 게이트 |
| `LIVE_AI_ASSIST` | AI 제안 + 사람 승인 | 🛑 게이트 |
| `FUTURES_AI_EXECUTION` | **영구 BLOCKED** | 🛑 영구 차단 |

## LIVE 활성화 blocker 체크리스트 (모두 충족해야 *검토* 가능)

1. 주식 MVP / Paper / Shadow / Manual / AI Assist 가 먼저 안정화.
2. 선물 모의 4주+ 운용 + 성과/리스크 기준 통과.
3. 1차 시장 *하나만* 선택 (국내 모의환경 우선, 해외선물 후순위).
4. `FuturesAIExecutionGate` 등 선물 전용 게이트 추가.
5. 거래 캘린더 + 롤오버 + 증거금 reconciliation 완료.
6. 운영자 별도 opt-in PR + 사용자 명시 승인.

## 코드 단 강제 (본 빌드)

- `ENABLE_FUTURES_LIVE_TRADING=false` 기본값 (config + .env.example).
- `FuturesRiskManager.evaluate_order` 는 LIVE 분기에서 **항상 REJECTED**.
- `route_futures_order` 는 paper-safe 모드가 아니면 `evaluate_order` 경로로 보내
  REJECTED 처리 (가상 체결 없음).
- `FuturesOrderExecutor.execute` 는 `is_live` broker 를 거부 (backstop).
- 실제 선물 broker LIVE 어댑터 코드 0개.
- 프론트엔드 "실거래(LIVE)" 버튼은 `disabled` 고정.

**FUTURES_AI_EXECUTION 은 본 프로젝트에서 영구 BLOCKED 이다** — 만기/롤오버
시점의 AI 자동매매는 어떤 단계에서도 금지한다.
