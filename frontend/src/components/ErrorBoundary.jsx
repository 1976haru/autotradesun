import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: String(error?.message || error) }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div role="alert" className="error-boundary">
          화면 일부에 문제가 발생했습니다. 새로고침 해주세요. ({this.state.message})
        </div>
      )
    }
    return this.props.children
  }
}
