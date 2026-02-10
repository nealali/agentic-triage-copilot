import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { apiJson, ApiError } from '../api/client'
import type { IssueOverview, DecisionCreate, AgentRun, Decision } from '../api/types'

export default function IssueDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [overview, setOverview] = useState<IssueOverview | null>(null)
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [runResult, setRunResult] = useState<AgentRun | null>(null)
  const [decideOpen, setDecideOpen] = useState(false)
  const [decideSubmitting, setDecideSubmitting] = useState(false)
  const [decideError, setDecideError] = useState<string | null>(null)
  const [closeModalOpen, setCloseModalOpen] = useState(false)
  const [closeReason, setCloseReason] = useState('')
  const [closeReviewer, setCloseReviewer] = useState('reviewer')
  const [closing, setClosing] = useState(false)
  const [form, setForm] = useState<DecisionCreate>({
    run_id: '',
    decision_type: 'APPROVE',
    final_action: 'QUERY_SITE',
    final_text: '',
    reviewer: 'reviewer',
    reason: undefined,
  })

  useEffect(() => {
    if (!id) return
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([
      apiJson<IssueOverview>(`/issues/${id}/overview`),
      apiJson<Decision[]>(`/issues/${id}/decisions`),
    ])
      .then(([overviewData, decisionsData]) => {
        if (!cancelled) {
          setOverview(overviewData)
          setDecisions(decisionsData)
          const runId = overviewData.latest_run?.run_id
          if (runId) setForm((f) => ({ ...f, run_id: runId, final_text: overviewData.latest_run ? '' : f.final_text }))
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : String(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [id])

  async function runAnalyze() {
    if (!id) return
    setAnalyzing(true)
    setRunResult(null)
    try {
      const run = await apiJson<AgentRun>(`/issues/${id}/analyze`, { method: 'POST', body: JSON.stringify({}) })
      setRunResult(run)
      setForm((f) => ({ ...f, run_id: run.run_id, final_text: run.recommendation.draft_message ?? '' }))
      setOverview((o) =>
        o
          ? {
            ...o,
            latest_run: {
              run_id: run.run_id,
              created_at: run.created_at,
              severity: run.recommendation.severity,
              action: run.recommendation.action,
              confidence: run.recommendation.confidence,
            },
            runs_count: o.runs_count + 1,
          }
          : null
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err))
    } finally {
      setAnalyzing(false)
    }
  }

  function openCloseModal() {
    setCloseReason('')
    setCloseReviewer(form.reviewer || 'reviewer')
    setCloseModalOpen(true)
  }

  async function submitClose(e: React.FormEvent) {
    e.preventDefault()
    if (!id || !closeReason.trim() || !closeReviewer.trim()) return
    const runId = overview?.latest_run?.run_id ?? runResult?.run_id
    if (!runId) return
    setClosing(true)
    setError(null)
    try {
      await apiJson(`/issues/${id}/decisions`, {
        method: 'POST',
        body: JSON.stringify({
          run_id: runId,
          decision_type: 'APPROVE',
          final_action: 'IGNORE',
          final_text: closeReason.trim(),
          reviewer: closeReviewer.trim(),
        }),
      })
      setCloseModalOpen(false)
      const [overviewData, decisionsData] = await Promise.all([
        apiJson<IssueOverview>(`/issues/${id}/overview`),
        apiJson<Decision[]>(`/issues/${id}/decisions`),
      ])
      setOverview(overviewData)
      setDecisions(decisionsData)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err))
    } finally {
      setClosing(false)
    }
  }

  async function submitDecision(e: React.FormEvent) {
    e.preventDefault()
    if (!id || !form.run_id) return
    setDecideSubmitting(true)
    setDecideError(null)
    try {
      await apiJson(`/issues/${id}/decisions`, {
        method: 'POST',
        body: JSON.stringify({
          run_id: form.run_id,
          decision_type: form.decision_type,
          final_action: form.final_action,
          final_text: form.final_text,
          reviewer: form.reviewer,
          reason: form.decision_type === 'OVERRIDE' ? form.reason : undefined,
        }),
      })
      setDecideOpen(false)
      setOverview(null)
      setLoading(true)
      const [overviewData, decisionsData] = await Promise.all([
        apiJson<IssueOverview>(`/issues/${id}/overview`),
        apiJson<Decision[]>(`/issues/${id}/decisions`),
      ])
      setOverview(overviewData)
      setDecisions(decisionsData)
    } catch (err) {
      setDecideError(err instanceof ApiError ? err.message : String(err))
    } finally {
      setDecideSubmitting(false)
    }
  }

  if (!id) return null
  if (loading && !overview) return <p className="text-gray-500">Loading…</p>
  if (error && !overview) {
    return (
      <div>
        <p className="text-red-600">{error}</p>
        <button type="button" onClick={() => navigate('/issues')} className="mt-2 text-blue-600 hover:underline">
          Back to issues
        </button>
      </div>
    )
  }
  if (!overview) return null

  const { issue, latest_run, latest_decision, recent_audit_events } = overview
  const rec = runResult?.recommendation ?? (latest_run ? { severity: latest_run.severity, action: latest_run.action, confidence: latest_run.confidence, rationale: '', draft_message: null } : null)

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <button type="button" onClick={() => navigate('/issues')} className="text-gray-600 hover:text-gray-900">
          ← Issues
        </button>
        <h1 className="text-xl font-semibold">Issue {issue.issue_id.slice(0, 8)}…</h1>
      </div>
      <div className="grid gap-4">
        <section className="bg-white border rounded p-4">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-medium text-gray-700">Overview</h2>
            {issue.status !== 'closed' && (
              <button
                type="button"
                onClick={openCloseModal}
                disabled={closing || (!latest_run && !runResult)}
                className="bg-gray-600 text-white px-3 py-1 rounded text-sm hover:bg-gray-700 disabled:opacity-50"
                title={!latest_run && !runResult ? 'Run analyze first to close' : undefined}
              >
                {closing ? 'Closing…' : 'Close issue'}
              </button>
            )}
          </div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-gray-500">Domain</dt>
            <dd>{issue.domain}</dd>
            <dt className="text-gray-500">Subject</dt>
            <dd>{issue.subject_id}</dd>
            <dt className="text-gray-500">Status</dt>
            <dd>
              <span className={`px-2 py-0.5 rounded ${issue.status === 'open' ? 'bg-amber-100' : issue.status === 'triaged' ? 'bg-blue-100' : 'bg-gray-200'}`}>
                {issue.status}
              </span>
            </dd>
            <dt className="text-gray-500">Description</dt>
            <dd>{issue.description}</dd>
          </dl>
        </section>

        <section className="bg-white border rounded p-4">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-medium text-gray-700">Analysis</h2>
            <button
              type="button"
              onClick={runAnalyze}
              disabled={analyzing}
              className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {analyzing ? 'Running…' : 'Run analyze'}
            </button>
          </div>
          {rec && (
            <div className="text-sm space-y-1 p-3 bg-gray-50 rounded">
              <p><span className="text-gray-500">Severity:</span> {rec.severity} · Action: {rec.action} · Confidence: {rec.confidence}</p>
              {'rationale' in rec && rec.rationale && <p><span className="text-gray-500">Rationale:</span> {rec.rationale}</p>}
              {'draft_message' in rec && rec.draft_message && <p><span className="text-gray-500">Draft message:</span> {rec.draft_message}</p>}
            </div>
          )}
          {!rec && !analyzing && <p className="text-gray-500 text-sm">No run yet. Click “Run analyze”.</p>}
        </section>

        <section className="bg-white border rounded p-4">
          <h2 className="font-medium text-gray-700 mb-2">Decision history</h2>
          {decisions.length === 0 ? (
            <p className="text-sm text-gray-500">No decisions yet.</p>
          ) : (
            <ul className="space-y-3">
              {decisions.map((d) => (
                <li key={d.decision_id} className="border-l-2 border-gray-200 pl-3 py-1">
                  <p className="text-sm font-medium">{d.decision_type} · {d.final_action} by {d.reviewer}</p>
                  <p className="text-xs text-gray-500">{d.timestamp}</p>
                  <p className="text-sm text-gray-600 mt-1">{d.final_text}</p>
                  {d.reason && <p className="text-xs text-amber-700 mt-1">Reason: {d.reason}</p>}
                </li>
              ))}
            </ul>
          )}
        </section>

        {issue.status !== 'closed' && (
          <section className="bg-white border rounded p-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-medium text-gray-700">Record decision</h2>
              <button
                type="button"
                onClick={() => setDecideOpen(true)}
                disabled={!latest_run && !runResult}
                className="bg-gray-700 text-white px-3 py-1 rounded text-sm hover:bg-gray-800 disabled:opacity-50"
              >
                Record decision
              </button>
            </div>
            <p className="text-xs text-gray-500">Record a decision for the latest analysis run. Close issue requires running analyze first.</p>
          </section>
        )}

        {recent_audit_events.length > 0 && (
          <section className="bg-white border rounded p-4">
            <h2 className="font-medium text-gray-700 mb-2">Recent audit</h2>
            <ul className="text-sm space-y-1">
              {recent_audit_events.map((ev) => (
                <li key={ev.event_id}>
                  <span className="text-gray-500">{ev.created_at}</span> {ev.event_type} — {ev.actor}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      {decideOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4" onClick={() => setDecideOpen(false)}>
          <div className="bg-white rounded-lg max-w-md w-full p-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold mb-3">Record decision</h3>
            <form onSubmit={submitDecision} className="space-y-3">
              <label className="block">
                <span className="text-sm text-gray-600">Decision type</span>
                <select
                  value={form.decision_type}
                  onChange={(e) => setForm((f) => ({ ...f, decision_type: e.target.value as DecisionCreate['decision_type'] }))}
                  className="w-full border rounded px-2 py-1"
                >
                  <option value="APPROVE">APPROVE</option>
                  <option value="OVERRIDE">OVERRIDE</option>
                  <option value="EDIT">EDIT</option>
                </select>
              </label>
              <label className="block">
                <span className="text-sm text-gray-600">Final action</span>
                <select
                  value={form.final_action}
                  onChange={(e) => setForm((f) => ({ ...f, final_action: e.target.value as DecisionCreate['final_action'] }))}
                  className="w-full border rounded px-2 py-1"
                >
                  <option value="QUERY_SITE">QUERY_SITE</option>
                  <option value="DATA_FIX">DATA_FIX</option>
                  <option value="MEDICAL_REVIEW">MEDICAL_REVIEW</option>
                  <option value="IGNORE">IGNORE</option>
                </select>
              </label>
              <label className="block">
                <span className="text-sm text-gray-600">Final text</span>
                <textarea
                  value={form.final_text}
                  onChange={(e) => setForm((f) => ({ ...f, final_text: e.target.value }))}
                  className="w-full border rounded px-2 py-1"
                  rows={2}
                  required
                />
              </label>
              <label className="block">
                <span className="text-sm text-gray-600">Reviewer</span>
                <input
                  value={form.reviewer}
                  onChange={(e) => setForm((f) => ({ ...f, reviewer: e.target.value }))}
                  className="w-full border rounded px-2 py-1"
                  required
                />
              </label>
              {form.decision_type === 'OVERRIDE' && (
                <label className="block">
                  <span className="text-sm text-gray-600">Reason (required for override)</span>
                  <input
                    value={form.reason ?? ''}
                    onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value || undefined }))}
                    className="w-full border rounded px-2 py-1"
                  />
                </label>
              )}
              {decideError && <p className="text-sm text-red-600">{decideError}</p>}
              <div className="flex gap-2 pt-2">
                <button type="submit" disabled={decideSubmitting} className="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 disabled:opacity-50">
                  {decideSubmitting ? 'Saving…' : 'Save'}
                </button>
                <button type="button" onClick={() => setDecideOpen(false)} className="bg-gray-200 px-3 py-1 rounded hover:bg-gray-300">
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {closeModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4" onClick={() => !closing && setCloseModalOpen(false)}>
          <div className="bg-white rounded-lg max-w-md w-full p-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold mb-3">Close issue</h3>
            <p className="text-sm text-gray-600 mb-3">This will record a closure decision (IGNORE) and show it in Decision history. Run analyze first if you have not yet.</p>
            <form onSubmit={submitClose} className="space-y-3">
              <label className="block">
                <span className="text-sm text-gray-600">Reason for closure <span className="text-red-500">*</span></span>
                <textarea
                  value={closeReason}
                  onChange={(e) => setCloseReason(e.target.value)}
                  className="w-full border rounded px-2 py-1"
                  rows={3}
                  required
                  placeholder="e.g. Accepted as-is; no action needed."
                />
              </label>
              <label className="block">
                <span className="text-sm text-gray-600">Reviewer <span className="text-red-500">*</span></span>
                <input
                  value={closeReviewer}
                  onChange={(e) => setCloseReviewer(e.target.value)}
                  className="w-full border rounded px-2 py-1"
                  required
                />
              </label>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <div className="flex gap-2 pt-2">
                <button type="submit" disabled={closing || !closeReason.trim() || !closeReviewer.trim()} className="bg-gray-600 text-white px-3 py-1 rounded hover:bg-gray-700 disabled:opacity-50">
                  {closing ? 'Closing…' : 'Close issue'}
                </button>
                <button type="button" onClick={() => setCloseModalOpen(false)} disabled={closing} className="bg-gray-200 px-3 py-1 rounded hover:bg-gray-300">
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
