import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import FuturesTab from './FuturesTab.jsx'
import { api } from '../services/backend/api.js'

vi.mock('../services/backend/api.js', () => ({
  api: {
    futuresContracts: vi.fn(),
    autoStatus: vi.fn(),
    autoStart: vi.fn(),
    autoStop: vi.fn(),
    positions: vi.fn(),
    audit: vi.fn(),
  },
}))

const stopped = { running: false, mode: 'SIMULATION', contract: 'KOSPI200_2603', tick_count: 0, order_count: 0, reject_count: 0, last_price: null, is_live_authorization: false }
const running = { ...stopped, running: true, tick_count: 1, last_price: 351 }
const pos = { balance: { cash: 50000000 }, positions: [], realized_pnl: 0 }
const audit = { count: 0, entries: [] }
const contracts = { contracts: [{ code: 'KOSPI200_2603', display_name: 'KOSPI200 선물 (2603)' }] }

beforeEach(() => {
  api.futuresContracts.mockResolvedValue(contracts)
  api.autoStatus.mockResolvedValue(stopped)
  api.positions.mockResolvedValue(pos)
  api.audit.mockResolvedValue(audit)
  api.autoStart.mockResolvedValue(running)
  api.autoStop.mockResolvedValue(stopped)
})

afterEach(() => vi.clearAllMocks())

describe('FuturesTab', () => {
  it('renders stopped state initially', async () => {
    render(<FuturesTab />)
    await waitFor(() => expect(screen.getByTestId('running-state')).toHaveTextContent('STOPPED'))
  })

  it('start button calls autoStart and shows RUNNING', async () => {
    render(<FuturesTab />)
    await waitFor(() => expect(screen.getByTestId('start-button')).toBeEnabled())
    fireEvent.click(screen.getByTestId('start-button'))
    await waitFor(() => {
      expect(api.autoStart).toHaveBeenCalled()
      expect(screen.getByTestId('running-state')).toHaveTextContent('RUNNING')
    })
  })

  it('stop button calls autoStop', async () => {
    api.autoStatus.mockResolvedValue(running)
    render(<FuturesTab />)
    await waitFor(() => expect(screen.getByTestId('running-state')).toHaveTextContent('RUNNING'))
    fireEvent.click(screen.getByTestId('stop-button'))
    await waitFor(() => expect(api.autoStop).toHaveBeenCalled())
  })

  it('LIVE button is always disabled (invariant)', async () => {
    render(<FuturesTab />)
    expect(screen.getByTestId('live-button')).toBeDisabled()
  })

  it('has no enabling LIVE labels like 실거래 시작 / Place Order', async () => {
    const { container } = render(<FuturesTab />)
    const text = container.textContent || ''
    expect(text).not.toContain('실거래 시작')
    expect(text).not.toContain('Place Order')
    // LIVE 버튼이 있어도 disabled 라벨이어야 함
    const liveBtn = screen.getByTestId('live-button')
    expect(liveBtn).toBeDisabled()
  })

  it('shows backend-down banner when status fails', async () => {
    api.autoStatus.mockRejectedValue(new Error('fail'))
    api.positions.mockRejectedValue(new Error('fail'))
    api.audit.mockRejectedValue(new Error('fail'))
    render(<FuturesTab />)
    await waitFor(() => expect(screen.getByTestId('backend-down-banner')).toBeInTheDocument())
  })
})
