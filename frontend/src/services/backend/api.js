// 단일 fetch wrapper — 모든 backend 호출은 여기로. 실제 시세/주문은 backend 에서만.
const BASE = import.meta.env?.VITE_BACKEND_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export const api = {
  status: () => request('/api/status'),
  futuresContracts: () => request('/api/futures/contracts'),
  autoStatus: () => request('/api/futures/auto/status'),
  autoStart: () => request('/api/futures/auto/start', { method: 'POST' }),
  autoStop: () => request('/api/futures/auto/stop', { method: 'POST' }),
  autoTick: () => request('/api/futures/auto/tick', { method: 'POST' }),
  positions: () => request('/api/futures/positions'),
  audit: () => request('/api/futures/audit'),
}
