import { useState, useCallback } from 'react'
import type { ApiFetcher, QueryResponse } from '../types'
import './QueryInterface.css'
import { ResultsTable } from './ResultsTable'
import { DisambiguationPicker } from './DisambiguationPicker'

type Props = { api: ApiFetcher }

type Message = { role: 'user' | 'assistant'; content: string; response?: QueryResponse }

export function QueryInterface({ api }: Props) {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [pendingDisambiguation, setPendingDisambiguation] = useState<{
    question: string
    choices: { dataset_id: string; label: string; why: string }[]
  } | null>(null)
  const sendQuery = useCallback(
    async (question: string, datasetId?: string) => {
      if (!question.trim()) return
      setMessages((m) => [...m, { role: 'user', content: question }])
      setInput('')
      setLoading(true)
      setPendingDisambiguation(null)

      try {
        const body = datasetId
          ? { question, dataset_id: datasetId }
          : { question, preferred_dataset: null }
        const path = datasetId ? '/nlq/disambiguate' : '/nlq/query'
        const res = (await api(path, {
          method: 'POST',
          body: JSON.stringify(body),
        }        )) as QueryResponse

        if (res.status === 'needs_selection' && res.choices) {
          setPendingDisambiguation({ question, choices: res.choices })
        } else if (res.status === 'needs_clarification') {
          setMessages((m) => [
            ...m,
            {
              role: 'assistant',
              content: res.clarifying_question,
              response: res,
            },
          ])
        } else if (res.status === 'ok') {
          const summary =
            res.results?.rows?.length != null
              ? `${res.results.rows.length} rows · ${res.explanation?.notes || 'Query completed'}`
              : res.explanation?.notes || 'Query completed'
          setMessages((m) => [
            ...m,
            { role: 'assistant', content: summary, response: res },
          ])
        } else {
          setMessages((m) => [
            ...m,
            { role: 'assistant', content: (res as { message?: string }).message || 'An error occurred.', response: res },
          ])
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Request failed'
        setMessages((m) => [...m, { role: 'assistant', content: msg }])
      } finally {
        setLoading(false)
      }
    },
    [api]
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    sendQuery(input.trim())
  }

  const handleDisambiguate = (datasetId: string) => {
    if (pendingDisambiguation) {
      sendQuery(pendingDisambiguation.question, datasetId)
      setPendingDisambiguation(null)
    }
  }

  return (
    <div className="query-interface">
      <div className="chat-panel">
        {messages.map((msg, i) => (
          <div key={i} className={`msg msg-${msg.role}`}>
            <div className="msg-role">{msg.role === 'user' ? 'You' : 'AI'}</div>
            <div className="msg-content">{msg.content}</div>
            {msg.response && msg.response.status === 'ok' && (
              <div className="msg-results">
                <ResultsTable response={msg.response} />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="msg msg-assistant">
            <div className="msg-role">AI</div>
            <div className="msg-content typing">Thinking...</div>
          </div>
        )}
      </div>

      {pendingDisambiguation && (
        <DisambiguationPicker
          choices={pendingDisambiguation.choices}
          onSelect={handleDisambiguate}
          onCancel={() => setPendingDisambiguation(null)}
        />
      )}

      <form className="input-form" onSubmit={handleSubmit}>
        <input
          type="text"
          className="input-field"
          placeholder="Ask about mortgage delinquency, rates, or house prices..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
        />
        <button type="submit" className="submit-btn" disabled={loading || !input.trim()}>
          Ask
        </button>
      </form>
    </div>
  )
}
