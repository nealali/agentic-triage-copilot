import { useState, useEffect } from 'react'
import { apiJson, ApiError, getApiBase } from '../api/client'

interface Document {
  doc_id: string
  created_at: string
  title: string
  source: string
  tags: string[]
  content: string
}

interface DocumentHit {
  doc_id: string
  title: string
  source: string
  score: number
  snippet: string
}

interface DocumentCreate {
  title: string
  source: string
  tags: string[]
  content: string
}

export default function Documents() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [searchResults, setSearchResults] = useState<DocumentHit[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [form, setForm] = useState<DocumentCreate>({
    title: '',
    source: '',
    tags: [],
    content: '',
  })
  const [tagInput, setTagInput] = useState('')

  useEffect(() => {
    loadDocuments()
  }, [])

  // Debounced search effect - triggers search automatically as user types
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([])
      setSearching(false)
      return
    }

    // Debounce: wait 300ms after user stops typing before searching
    const timeoutId = setTimeout(() => {
      performSearch(searchQuery.trim())
    }, 300)

    return () => clearTimeout(timeoutId)
  }, [searchQuery])

  async function loadDocuments() {
    setLoading(true)
    setError(null)
    try {
      const docs = await apiJson<Document[]>('/documents')
      setDocuments(docs)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  async function performSearch(query: string) {
    if (!query.trim()) {
      setSearchResults([])
      return
    }

    setSearching(true)
    setError(null)
    try {
      const results = await apiJson<DocumentHit[]>(`/documents/search?q=${encodeURIComponent(query)}&limit=20`)
      setSearchResults(results)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err))
      setSearchResults([])
    } finally {
      setSearching(false)
    }
  }

  function clearSearch() {
    setSearchQuery('')
    setSearchResults([])
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault()
    if (!form.title.trim() || !form.source.trim() || !form.content.trim()) {
      setUploadError('Title, source, and content are required')
      return
    }

    setUploading(true)
    setUploadError(null)
    try {
      await apiJson<Document>('/documents', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      setUploadOpen(false)
      setForm({ title: '', source: '', tags: [], content: '' })
      setTagInput('')
      await loadDocuments()
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        const useKey = window.confirm(
          'Document upload requires authentication. Do you want to set an API key?\n\n' +
          'Click OK to set API key, or Cancel to close.'
        )
        if (useKey) {
          const key = window.prompt('Enter API key:')
          if (key) {
            sessionStorage.setItem('apiKey', key)
            window.location.reload()
            return
          }
        }
        setUploadError('Authentication required. Please set API key.')
      } else {
        setUploadError(err instanceof ApiError ? err.message : String(err))
      }
    } finally {
      setUploading(false)
    }
  }

  function addTag() {
    const tag = tagInput.trim()
    if (tag && !form.tags.includes(tag)) {
      setForm((f) => ({ ...f, tags: [...f.tags, tag] }))
      setTagInput('')
    }
  }

  function removeTag(tag: string) {
    setForm((f) => ({ ...f, tags: f.tags.filter((t) => t !== tag) }))
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">RAG Documents</h1>
        <button
          type="button"
          onClick={() => setUploadOpen(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
        >
          + Upload Document
        </button>
      </div>

      <p className="text-sm text-gray-600 mb-4">
        Guidance documents used for RAG (Retrieval-Augmented Generation). These documents provide context and query templates for issue analysis.
      </p>

      {/* Search Section */}
      <div className="mb-4 bg-white border rounded p-4">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search documents by keyword..."
              className="w-full border rounded px-3 py-2 pr-10"
            />
            {searching && (
              <span className="absolute right-3 top-2.5 text-gray-400 text-xs">Searching...</span>
            )}
          </div>
          {searchQuery && (
            <button
              type="button"
              onClick={clearSearch}
              className="bg-gray-200 px-4 py-2 rounded hover:bg-gray-300"
            >
              Clear
            </button>
          )}
        </div>
        {searchQuery && searchResults.length > 0 && !searching && (
          <p className="text-xs text-gray-500 mt-2">
            Found {searchResults.length} document(s) matching "{searchQuery}"
          </p>
        )}
        {searchQuery && searchResults.length === 0 && !searching && (
          <p className="text-xs text-gray-500 mt-2">
            No documents found matching "{searchQuery}"
          </p>
        )}
      </div>

      {uploadOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full p-6 shadow-xl max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold mb-4">Upload New Document</h2>
            <form onSubmit={handleUpload} className="space-y-4">
              <label className="block">
                <span className="text-sm text-gray-600">Title <span className="text-red-500">*</span></span>
                <input
                  type="text"
                  value={form.title}
                  onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                  className="w-full border rounded px-2 py-1"
                  required
                  placeholder="e.g., AE Date Consistency Checks"
                />
              </label>
              <label className="block">
                <span className="text-sm text-gray-600">Source <span className="text-red-500">*</span></span>
                <input
                  type="text"
                  value={form.source}
                  onChange={(e) => setForm((f) => ({ ...f, source: e.target.value }))}
                  className="w-full border rounded px-2 py-1"
                  required
                  placeholder="e.g., DRP, SOP, SDTM_Guide"
                />
              </label>
              <label className="block">
                <span className="text-sm text-gray-600">Tags</span>
                <div className="flex gap-2 mb-2">
                  <input
                    type="text"
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addTag())}
                    className="flex-1 border rounded px-2 py-1"
                    placeholder="Add tag and press Enter"
                  />
                  <button type="button" onClick={addTag} className="bg-gray-200 px-3 py-1 rounded hover:bg-gray-300">
                    Add
                  </button>
                </div>
                {form.tags.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {form.tags.map((tag) => (
                      <span key={tag} className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-sm flex items-center gap-1">
                        {tag}
                        <button
                          type="button"
                          onClick={() => removeTag(tag)}
                          className="text-blue-600 hover:text-blue-800"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </label>
              <label className="block">
                <span className="text-sm text-gray-600">Content <span className="text-red-500">*</span></span>
                <textarea
                  value={form.content}
                  onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))}
                  className="w-full border rounded px-2 py-1"
                  rows={10}
                  required
                  placeholder="Document content (guidance, query templates, etc.)"
                />
              </label>
              {uploadError && <p className="text-sm text-red-600">{uploadError}</p>}
              <div className="flex gap-2 pt-2">
                <button
                  type="submit"
                  disabled={uploading}
                  className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
                >
                  {uploading ? 'Uploading…' : 'Upload'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setUploadOpen(false)
                    setForm({ title: '', source: '', tags: [], content: '' })
                    setTagInput('')
                    setUploadError(null)
                  }}
                  className="bg-gray-200 px-4 py-2 rounded hover:bg-gray-300"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {loading && <p className="text-gray-500">Loading documents...</p>}
      {error && (
        <div className="p-3 bg-red-50 text-red-800 rounded border border-red-200">
          {error}
        </div>
      )}

      {!loading && !error && (
        <>
          {searchQuery ? (
            // Show search results
            <>
              {searchResults.length === 0 ? (
                <p className="text-gray-500">No documents found matching "{searchQuery}". Try different keywords.</p>
              ) : (
                <div className="space-y-4">
                  <p className="text-sm text-gray-600">
                    Search results: {searchResults.length} document(s) found
                  </p>
                  {searchResults.map((hit) => (
                    <div key={hit.doc_id} className="bg-white border rounded p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h3 className="font-medium text-gray-900">{hit.title}</h3>
                          <p className="text-sm text-gray-500 mt-1">
                            Source: {hit.source} • Relevance score: {(hit.score * 100).toFixed(1)}%
                          </p>
                          <p className="text-sm text-gray-600 mt-2 bg-gray-50 p-2 rounded">
                            <span className="font-medium">Snippet:</span> {hit.snippet}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            // Show all documents
            <>
              {documents.length === 0 ? (
                <p className="text-gray-500">No documents found. Upload a document to get started.</p>
              ) : (
                <div className="space-y-4">
                  <p className="text-sm text-gray-600">Total: {documents.length} document(s)</p>
                  {documents.map((doc) => (
                    <div key={doc.doc_id} className="bg-white border rounded p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h3 className="font-medium text-gray-900">{doc.title}</h3>
                          <p className="text-sm text-gray-500 mt-1">
                            Source: {doc.source} • Created: {new Date(doc.created_at).toLocaleString()}
                          </p>
                          {doc.tags.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {doc.tags.map((tag) => (
                                <span key={tag} className="bg-gray-100 text-gray-700 px-2 py-0.5 rounded text-xs">
                                  {tag}
                                </span>
                              ))}
                            </div>
                          )}
                          <details className="mt-3">
                            <summary className="cursor-pointer text-sm text-blue-600 hover:text-blue-800">
                              View content
                            </summary>
                            <pre className="mt-2 p-3 bg-gray-50 rounded text-xs overflow-x-auto whitespace-pre-wrap">
                              {doc.content}
                            </pre>
                          </details>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
