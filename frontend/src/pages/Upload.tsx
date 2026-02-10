import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiUpload, ApiError, getApiBase } from '../api/client'
import type { IngestResponse } from '../api/types'

export default function Upload() {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<IngestResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!file) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const data = await apiUpload<IngestResponse>('/ingest/issues', form)
      setResult(data)
      if (data.created > 0) setFile(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Upload issues (Excel)</h1>
      <p className="text-gray-600 mb-4">
        Upload a .xlsx file (RAVE/QC export style). Max 200 rows, 5 MB. Columns: Source, Domain, Subject_ID, Fields, Description, and optional Start_Date, End_Date, Variable, Value, Reference, Notes.
      </p>
      <p className="text-xs text-gray-400 mb-2">API: {getApiBase()}</p>
      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">File</span>
          <input
            type="file"
            accept=".xlsx"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="border rounded px-3 py-2"
          />
        </label>
        <button
          type="submit"
          disabled={!file || loading}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Uploading…' : 'Upload'}
        </button>
      </form>
      {error && (
        <div className="mt-4 p-3 bg-red-50 text-red-800 rounded border border-red-200">
          {error}
        </div>
      )}
      {result && (
        <div className="mt-4 p-4 bg-green-50 rounded border border-green-200">
          <p className="font-medium text-green-800">Created {result.created} issue(s).</p>
          {result.errors.length > 0 && (
            <ul className="mt-2 text-sm text-amber-800 list-disc list-inside">
              {result.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
          {result.created > 0 && (
            <button
              type="button"
              onClick={() => navigate('/issues')}
              className="mt-3 text-blue-600 hover:underline"
            >
              View issues →
            </button>
          )}
        </div>
      )}
    </div>
  )
}
