import { useEffect, useState } from 'react'
import { apiJson, ApiError } from '../api/client'
import type { AuditEvent } from '../api/types'

export default function Audit() {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    apiJson<AuditEvent[]>('/audit')
      .then((data) => {
        if (!cancelled) setEvents(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : String(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Audit log</h1>
      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-800 rounded border border-red-200">
          {error}
        </div>
      )}
      {loading ? (
        <p className="text-gray-500">Loading…</p>
      ) : events.length === 0 ? (
        <p className="text-gray-500">No audit events.</p>
      ) : (
        <div className="border rounded overflow-hidden bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-100">
              <tr>
                <th className="text-left p-2">Time</th>
                <th className="text-left p-2">Type</th>
                <th className="text-left p-2">Actor</th>
                <th className="text-left p-2">Correlation ID</th>
                <th className="text-left p-2">Issue / Run</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => (
                <tr key={ev.event_id} className="border-t hover:bg-gray-50">
                  <td className="p-2 text-gray-600">{ev.created_at}</td>
                  <td className="p-2">{ev.event_type}</td>
                  <td className="p-2">{ev.actor}</td>
                  <td className="p-2 font-mono text-xs">{ev.correlation_id?.slice(0, 8)}…</td>
                  <td className="p-2">
                    {ev.issue_id && <span className="font-mono text-xs">{ev.issue_id.slice(0, 8)}…</span>}
                    {ev.run_id && <span className="ml-1 font-mono text-xs">run {ev.run_id.slice(0, 8)}…</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
