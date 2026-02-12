import type { QueryResponse } from '../types'
import './ResultsTable.css'

type Props = { response: QueryResponse }

export function ResultsTable({ response }: Props) {
  if (response.status !== 'ok' || !response.results) return null
  const { columns, rows } = response.results
  if (!columns?.length && !rows?.length) return null

  return (
    <div className="results-block">
      <details className="sql-details">
        <summary>View SQL</summary>
        <pre className="sql-code">{response.sql}</pre>
      </details>
      {response.explanation?.tables?.length ? (
        <p className="results-meta">Tables: {response.explanation.tables.join(', ')}</p>
      ) : null}
      <div className="table-wrap">
        <table className="results-table">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 100).map((row, i) => (
              <tr key={i}>
                {columns.map((col) => (
                  <td key={col}>{formatCell(row[col])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > 100 && <p className="results-truncated">Showing first 100 of {rows.length} rows</p>}
    </div>
  )
}

function formatCell(val: unknown): string {
  if (val == null) return '—'
  if (typeof val === 'number') return val.toLocaleString()
  return String(val)
}
