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
  const [useLLM, setUseLLM] = useState(false)
  const [useSemanticRAG, setUseSemanticRAG] = useState(false)
  const [form, setForm] = useState<DecisionCreate>({
    run_id: '',
    decision_type: 'APPROVE',
    final_action: 'QUERY_SITE',
    final_text: '',
    reviewer: 'reviewer',
    reason: undefined,
    specify: undefined,
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

          // Set default checkboxes based on issue type
          // Deterministic issues: default to false (no LLM, no semantic RAG)
          // LLM-required issues: default to true (forced on anyway, but set for consistency)
          if (overviewData.issue.issue_type === 'deterministic') {
            setUseLLM(false)
            setUseSemanticRAG(false)
            // Clear sessionStorage for deterministic issues so defaults persist
            sessionStorage.removeItem('analyze_use_llm')
            sessionStorage.removeItem('analyze_use_semantic_rag')
          } else if (overviewData.issue.issue_type === 'llm_required') {
            // LLM-required issues always use LLM+RAG, but check sessionStorage for user preference
            // (though it won't matter since they're forced on)
            const savedLLM = sessionStorage.getItem('analyze_use_llm')
            const savedRAG = sessionStorage.getItem('analyze_use_semantic_rag')
            setUseLLM(savedLLM ? savedLLM === 'true' : true)
            setUseSemanticRAG(savedRAG ? savedRAG === 'true' : true)
          } else {
            // Fallback: check sessionStorage
            const savedLLM = sessionStorage.getItem('analyze_use_llm')
            const savedRAG = sessionStorage.getItem('analyze_use_semantic_rag')
            setUseLLM(savedLLM ? savedLLM === 'true' : false)
            setUseSemanticRAG(savedRAG ? savedRAG === 'true' : false)
          }

          const runId = overviewData.latest_run?.run_id
          if (runId) {
            setForm((f) => ({ ...f, run_id: runId, final_text: overviewData.latest_run ? '' : f.final_text }))
            // Fetch full run to get rationale and draft_message
            apiJson<AgentRun>(`/issues/${id}/runs/${runId}`)
              .then((fullRun) => {
                if (!cancelled) {
                  setRunResult(fullRun)
                }
              })
              .catch(() => {
                // Ignore errors - will fall back to summary view
              })
          }
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
    if (!id || !overview) return
    setAnalyzing(true)
    setRunResult(null)
    try {
      // For LLM-required issues, force LLM+RAG (cannot be overridden)
      const issueRequiresLLM = overview.issue.issue_type === 'llm_required'
      const body = {
        use_llm: issueRequiresLLM || useLLM,
        use_semantic_rag: issueRequiresLLM || useSemanticRAG,
      }
      const run = await apiJson<AgentRun>(`/issues/${id}/analyze`, { method: 'POST', body: JSON.stringify(body) })
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
          specify: form.final_action === 'OTHER' ? form.specify : undefined,
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
            <dt className="text-gray-500">Type</dt>
            <dd>
              <span className={`px-2 py-0.5 rounded text-xs ${issue.issue_type === 'llm_required' ? 'bg-purple-100 text-purple-800' : 'bg-green-100 text-green-800'}`} title={issue.issue_type === 'llm_required' ? 'Requires LLM+RAG analysis' : 'Deterministic rule-based analysis'}>
                {issue.issue_type === 'llm_required' ? 'LLM Required' : 'Deterministic'}
              </span>
            </dd>
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
          <div className="flex items-center justify-between mb-3">
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
          <div className="flex flex-wrap gap-4 mb-3 text-sm">
            {issue.issue_type === 'llm_required' && (
              <div className="w-full text-xs text-purple-700 bg-purple-50 px-2 py-1 rounded">
                This issue is classified as LLM-required and will automatically use LLM+RAG for analysis.
              </div>
            )}
            <label className="flex items-center gap-2 cursor-pointer" title="Enhance recommendations with LLM reasoning (requires OPENAI_API_KEY)">
              <input
                type="checkbox"
                checked={useLLM || issue.issue_type === 'llm_required'}
                disabled={issue.issue_type === 'llm_required'}
                onChange={(e) => {
                  setUseLLM(e.target.checked)
                  // Only save to sessionStorage for non-deterministic issues
                  // Deterministic issues should always default to false
                  if (issue.issue_type !== 'deterministic') {
                    sessionStorage.setItem('analyze_use_llm', String(e.target.checked))
                  }
                }}
                className="cursor-pointer"
              />
              <span className={`text-gray-700 ${issue.issue_type === 'llm_required' ? 'text-purple-700 font-medium' : ''}`}>
                Use LLM enhancement {issue.issue_type === 'llm_required' && '(required)'}
              </span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer" title="Use semantic search (embeddings) instead of keyword matching. Semantic RAG finds documents by meaning, not just exact word matches. It provides similarity scores (0-1) showing how relevant each document is.">
              <input
                type="checkbox"
                checked={useSemanticRAG || issue.issue_type === 'llm_required'}
                disabled={issue.issue_type === 'llm_required'}
                onChange={(e) => {
                  setUseSemanticRAG(e.target.checked)
                  // Only save to sessionStorage for non-deterministic issues
                  // Deterministic issues should always default to false
                  if (issue.issue_type !== 'deterministic') {
                    sessionStorage.setItem('analyze_use_semantic_rag', String(e.target.checked))
                  }
                }}
                className="cursor-pointer"
              />
              <span className={`text-gray-700 ${issue.issue_type === 'llm_required' ? 'text-purple-700 font-medium' : ''}`}>
                Use semantic RAG {issue.issue_type === 'llm_required' && '(required)'}
              </span>
            </label>
          </div>
          {rec && (
            <div className="text-sm space-y-1 p-3 bg-gray-50 rounded">
              <p><span className="text-gray-500">Severity:</span> {rec.severity} · Action: {rec.action} · Confidence: {rec.confidence}</p>
              {'rationale' in rec && rec.rationale && (
                <div>
                  <p><span className="text-gray-500">Rationale:</span> {rec.rationale}</p>
                  {runResult?.recommendation.tool_results?.llm_rationale_original && (
                    <p className="text-xs text-gray-400 mt-1 italic">
                      Original: {runResult.recommendation.tool_results.llm_rationale_original as string}
                    </p>
                  )}
                </div>
              )}
              {'draft_message' in rec && rec.draft_message && (
                <div>
                  <p><span className="text-gray-500">Draft message:</span> {rec.draft_message}</p>
                  {/* Warning when LLM generated a message but no citations were found */}
                  {runResult?.recommendation.tool_results.llm_enhanced &&
                    (!runResult.recommendation.citations || runResult.recommendation.citations.length === 0) && (
                      <div className="mt-2 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800">
                        <span className="font-medium">⚠️ Warning:</span> No citations found from RAG documents, but LLM still generated a draft message.
                        Please review carefully as this recommendation may not be grounded in documented guidance.
                      </div>
                    )}
                </div>
              )}
              {runResult?.recommendation.citations && runResult.recommendation.citations.length > 0 ? (
                <div className="mt-2">
                  <p className="text-gray-500 text-xs font-medium">
                    Citations ({runResult.recommendation.citations.length})
                    {runResult.recommendation.tool_results.rag_method === 'semantic' && (
                      <span className="text-purple-600 ml-1">(semantic search)</span>
                    )}
                  </p>
                  {runResult.recommendation.tool_results.citation_hits && (
                    <ul className="text-xs text-gray-600 mt-1 space-y-1">
                      {(runResult.recommendation.tool_results.citation_hits as Array<{ title: string, source: string, score?: number }>).slice(0, 3).map((hit, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span>•</span>
                          <span className="flex-1">
                            <span className="font-medium">{hit.title}</span>
                            <span className="text-gray-500"> ({hit.source})</span>
                            {runResult.recommendation.tool_results.rag_method === 'semantic' && hit.score !== undefined && (
                              <span className="text-purple-600 font-medium ml-1">
                                [similarity: {(hit.score * 100).toFixed(1)}%]
                              </span>
                            )}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                  <ul className="text-xs text-gray-400 list-disc list-inside mt-1">
                    {runResult.recommendation.citations.map((cid, idx) => (
                      <li key={idx}>{cid.slice(0, 8)}...</li>
                    ))}
                  </ul>
                </div>
              ) : runResult?.recommendation.tool_results.rag_method && (
                <div className="mt-2 text-xs text-gray-400">
                  No citations found. {runResult.recommendation.tool_results.rag_method === 'semantic'
                    ? 'Semantic search found no relevant documents.'
                    : 'Keyword search found no matching documents.'}
                </div>
              )}
              {runResult?.recommendation.tool_results && (
                <div className="mt-2 pt-2 border-t border-gray-300 text-xs">
                  <div className="text-gray-500 space-x-2">
                    {runResult.recommendation.tool_results.rag_method && (
                      <span className={runResult.recommendation.tool_results.rag_method === 'semantic' ? 'text-purple-600 font-medium' : ''} title={runResult.recommendation.tool_results.rag_method === 'semantic' ? 'Semantic RAG uses embeddings to find documents by meaning, providing similarity scores' : 'Keyword RAG uses exact word matching'}>
                        RAG: {runResult.recommendation.tool_results.rag_method}
                        {runResult.recommendation.tool_results.rag_method === 'semantic' && ' ✓'}
                      </span>
                    )}
                    {runResult.recommendation.tool_results.llm_enhanced && (
                      <span className="text-green-600 font-medium">
                        ✓ LLM: {runResult.recommendation.tool_results.llm_model || 'enabled'}
                      </span>
                    )}
                    {runResult.recommendation.tool_results.llm_requested && !runResult.recommendation.tool_results.llm_enhanced && (
                      <span className="text-amber-600">
                        ⚠ LLM requested but not enhanced
                        {runResult.recommendation.tool_results.llm_failure_reason && (
                          <div className="text-xs mt-1">{runResult.recommendation.tool_results.llm_failure_reason}</div>
                        )}
                        {!runResult.recommendation.tool_results.llm_failure_reason && (
                          <div className="text-xs mt-1">Check OPENAI_API_KEY in .env file and restart server</div>
                        )}
                      </span>
                    )}
                  </div>
                  {runResult.recommendation.tool_results.rag_method === 'semantic' && runResult.recommendation.citations && runResult.recommendation.citations.length > 0 && (
                    <div className="text-xs text-purple-600 mt-1 italic">
                      Semantic search found {runResult.recommendation.citations.length} relevant document{runResult.recommendation.citations.length !== 1 ? 's' : ''} with similarity scores above
                    </div>
                  )}
                </div>
              )}
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
                  {d.final_action === 'OTHER' && d.specify && (
                    <p className="text-xs text-blue-700 mt-1 font-medium">Specify: {d.specify}</p>
                  )}
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
                  <option value="OTHER">OTHER</option>
                </select>
              </label>
              {form.final_action === 'OTHER' && (
                <label className="block">
                  <span className="text-sm text-gray-600">Specify (required for OTHER) <span className="text-red-500">*</span></span>
                  <input
                    value={form.specify ?? ''}
                    onChange={(e) => setForm((f) => ({ ...f, specify: e.target.value || undefined }))}
                    className="w-full border rounded px-2 py-1"
                    placeholder="e.g., Escalate to data manager, Request protocol clarification"
                    required
                  />
                </label>
              )}
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
