import { useState } from 'react'
import { QueryInterface } from './components/QueryInterface'
import type { ApiFetcher } from './types'
import './App.css'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

function createFetcher(base: string): ApiFetcher {
  return async (path, opts = {}) => {
    const res = await fetch(`${base}${path}`, {
      ...opts,
      headers: { 'Content-Type': 'application/json', ...opts.headers },
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || data.message || res.statusText)
    return data
  }
}

export function App() {
  const [api] = useState(() => createFetcher(API_BASE))

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-icon">◆</span>
            <span className="logo-text">AI-Financer</span>
          </div>
          <p className="tagline">Natural Language to SQL for Mortgage & Credit Analytics</p>
        </div>
      </header>
      <main className="main">
        <QueryInterface api={api} />
      </main>
      <footer className="footer">
        <span>© {new Date().getFullYear()} Sai Santhosh V C · MIT License</span>
        <span>CPFB · FRED · FHFA Data</span>
      </footer>
    </div>
  )
}
