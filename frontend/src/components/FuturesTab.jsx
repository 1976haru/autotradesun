import { useCallback, useEffect, useState } from 'react'
import { api } from '../services/backend/api.js'

// 국내선물 모의/Paper 자동매매 관제 + "시작 버튼".
// 실거래(LIVE) 버튼은 항상 disabled 고정 — 본 빌드는 모의/Paper 범위.
export default function FuturesTab() {
  const [status, setStatus] = useState(null)
  const [positions, setPositions] = useState(null)
  const [audit, setAudit] = useState(null)
  const [contracts, setContracts] = useState([])
  const [backendDown, setBackendDown] = useState(false)
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [st, pos, au] = await Promise.all([
        api.autoStatus(),
        api.positions(),
        api.audit(),
      ])
      setStatus(st)
      setPositions(pos)
      setAudit(au)
      setBackendDown(false)
    } catch {
      setBackendDown(true)
    }
  }, [])

  useEffect(() => {
    api.futuresContracts().then((d) => setContracts(d.contracts || [])).catch(() => setBackendDown(true))
    refresh()
  }, [refresh])

  const onStart = async () => {
    setBusy(true)
    try {
      const st = await api.autoStart()
      setStatus(st)
      setBackendDown(false)
      await refresh()
    } catch {
      setBackendDown(true)
    } finally {
      setBusy(false)
    }
  }

  const onStop = async () => {
    setBusy(true)
    try {
      const st = await api.autoStop()
      setStatus(st)
      await refresh()
    } catch {
      setBackendDown(true)
    } finally {
      setBusy(false)
    }
  }

  const running = !!status?.running

  return (
    <section className="futures-tab">
      <h1>국내선물 모의 자동매매</h1>
      <p className="safety-note">
        본 화면은 <strong>모의/Paper</strong> 자동매매 관제용입니다. 실거래(LIVE)는
        비활성화되어 있으며 시작 버튼으로 켜지지 않습니다.
      </p>

      {backendDown && (
        <div role="alert" className="banner banner-warn" data-testid="backend-down-banner">
          백엔드에 연결할 수 없습니다. 백엔드(uvicorn)를 먼저 실행해 주세요.
        </div>
      )}

      <div className="controls">
        <button
          type="button"
          onClick={onStart}
          disabled={busy || running}
          data-testid="start-button"
        >
          국내선물 모의 자동매매 시작
        </button>
        <button
          type="button"
          onClick={onStop}
          disabled={busy || !running}
          data-testid="stop-button"
        >
          중지
        </button>
        {/* 실거래 버튼 — 항상 비활성 (본 빌드 범위 밖) */}
        <button type="button" disabled data-testid="live-button" title="실거래는 비활성화됨">
          실거래(LIVE) — 비활성
        </button>
      </div>

      <div className="status" data-testid="status-panel">
        <span data-testid="running-state">
          상태: {running ? 'RUNNING' : 'STOPPED'}
        </span>
        {status && (
          <ul>
            <li>모드: {status.mode}</li>
            <li>계약: {status.contract}</li>
            <li>tick: {status.tick_count}</li>
            <li>주문(가상): {status.order_count}</li>
            <li>거부: {status.reject_count}</li>
            <li>최근가: {status.last_price ?? '-'}</li>
            <li>실거래 권한: {String(status.is_live_authorization)}</li>
          </ul>
        )}
      </div>

      {positions && (
        <div className="positions" data-testid="positions-panel">
          <h2>포지션 / 잔고</h2>
          <p>현금: {positions.balance?.cash?.toLocaleString?.() ?? '-'} · 실현손익: {positions.realized_pnl?.toLocaleString?.() ?? '-'}</p>
          <p>보유 포지션: {positions.positions?.length ?? 0}건</p>
        </div>
      )}

      {audit && (
        <div className="audit" data-testid="audit-panel">
          <h2>주문 감사 로그 ({audit.count}건)</h2>
        </div>
      )}

      <div className="contracts" data-testid="contracts-panel">
        <h2>계약 ({contracts.length})</h2>
        <ul>
          {contracts.map((c) => (
            <li key={c.code}>{c.display_name} — {c.code}</li>
          ))}
        </ul>
      </div>
    </section>
  )
}
