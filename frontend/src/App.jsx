import ErrorBoundary from './components/ErrorBoundary.jsx'
import FuturesTab from './components/FuturesTab.jsx'

export default function App() {
  return (
    <ErrorBoundary>
      <FuturesTab />
    </ErrorBoundary>
  )
}
