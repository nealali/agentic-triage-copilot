import { useEffect, useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { apiJson, ApiError } from '../api/client'
import type { Issue } from '../api/types'

type StatusFilter = 'all' | 'open' | 'triaged' | 'closed'

export default function IssuesList() {
  const [issues, setIssues] = useState<Issue[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [domainFilter, setDomainFilter] = useState<string>('')
  const [subjectFilter, setSubjectFilter] = useState<string>('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    apiJson<Issue[]>('/issues')
      .then((data) => {
        if (!cancelled) setIssues(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : String(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  const domains = useMemo(() => {
    const set = new Set(issues.map((i) => i.domain).filter(Boolean))
    return Array.from(set).sort()
  }, [issues])

  const filtered = useMemo(() => {
    return issues.filter((i) => {
      if (statusFilter !== 'all' && i.status !== statusFilter) return false
      if (domainFilter && i.domain !== domainFilter) return false
      if (subjectFilter && !i.subject_id.toLowerCase().includes(subjectFilter.toLowerCase())) return false
      return true
    })
  }, [issues, statusFilter, domainFilter, subjectFilter])

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Issues</h1>
      <div className="flex flex-wrap items-center gap-4 mb-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">Status</span>
          {(['all', 'open', 'triaged', 'closed'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setStatusFilter(f)}
              className={`px-3 py-1 rounded text-sm ${statusFilter === f ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
            >
              {f === 'all' ? 'All' : f}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">Domain</label>
          <select
            value={domainFilter}
            onChange={(e) => setDomainFilter(e.target.value)}
            className="border rounded px-2 py-1 text-sm"
          >
            <option value="">All domains</option>
            {domains.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">Subject</label>
          <input
            type="text"
            placeholder="Filter by subject ID"
            value={subjectFilter}
            onChange={(e) => setSubjectFilter(e.target.value)}
            className="border rounded px-2 py-1 text-sm w-48"
          />
        </div>
      </div>
      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-800 rounded border border-red-200">
          {error}
        </div>
      )}
      {loading ? (
        <p className="text-gray-500">Loading…</p>
      ) : filtered.length === 0 ? (
        <p className="text-gray-500">No issues match the filters. Upload an Excel file from the Upload page or clear filters.</p>
      ) : (
        <div className="border rounded overflow-hidden bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-100">
              <tr>
                <th className="text-left p-2">ID</th>
                <th className="text-left p-2">Domain</th>
                <th className="text-left p-2">Subject</th>
                <th className="text-left p-2">Type</th>
                <th className="text-left p-2">Status</th>
                <th className="text-left p-2">Description</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((i) => (
                <tr key={i.issue_id} className="border-t hover:bg-gray-50">
                  <td className="p-2 font-mono text-xs">
                    <Link to={`/issues/${i.issue_id}`} className="text-blue-600 hover:underline">
                      {i.issue_id.slice(0, 8)}…
                    </Link>
                  </td>
                  <td className="p-2">{i.domain}</td>
                  <td className="p-2">{i.subject_id}</td>
                  <td className="p-2">
                    <span className={`px-2 py-0.5 rounded text-xs ${i.issue_type === 'llm_required' ? 'bg-purple-100 text-purple-800' : 'bg-green-100 text-green-800'}`} title={i.issue_type === 'llm_required' ? 'Requires LLM+RAG analysis' : 'Deterministic rule-based analysis'}>
                      {i.issue_type === 'llm_required' ? 'LLM' : 'Rule'}
                    </span>
                  </td>
                  <td className="p-2">
                    <span className={`px-2 py-0.5 rounded ${i.status === 'open' ? 'bg-amber-100' : i.status === 'triaged' ? 'bg-blue-100' : 'bg-gray-200'}`}>
                      {i.status}
                    </span>
                  </td>
                  <td className="p-2 max-w-xs truncate">{i.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
