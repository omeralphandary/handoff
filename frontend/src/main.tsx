import { StrictMode, Component } from 'react'
import type { ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

interface EBState { error: Error | null }
class ErrorBoundary extends Component<{ children: ReactNode }, EBState> {
  state: EBState = { error: null }
  static getDerivedStateFromError(error: Error): EBState { return { error } }
  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-zinc-950 text-zinc-200 flex items-center justify-center p-8">
          <div className="max-w-lg w-full">
            <p className="text-red-400 font-mono text-sm mb-2">Render error:</p>
            <pre className="text-xs text-zinc-400 bg-zinc-900 border border-zinc-800 rounded p-4 overflow-auto whitespace-pre-wrap">
              {this.state.error.message}
              {'\n\n'}
              {this.state.error.stack}
            </pre>
          </div>
        </div>
      )
    }
    return this.state.error === null ? this.props.children : null
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
