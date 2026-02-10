/**
 * API client for the FastAPI backend.
 * Uses VITE_API_BASE_URL (default http://localhost:8000). When AUTH_ENABLED=1,
 * send X-API-Key from sessionStorage.
 */

const BASE = (import.meta as unknown as { env: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL ?? 'http://localhost:8000'

export function getApiBase(): string {
  return BASE
}

function headers(extra: HeadersInit = {}, omitContentType = false): HeadersInit {
  const h: Record<string, string> = { ...(extra as Record<string, string>) }
  if (!omitContentType) h['Content-Type'] = 'application/json'
  const key = sessionStorage.getItem('apiKey')
  if (key) h['X-API-Key'] = key
  return h
}

export async function apiFetch(path: string, options: RequestInit & { omitContentType?: boolean } = {}): Promise<Response> {
  const { omitContentType, ...rest } = options
  const url = path.startsWith('http') ? path : `${BASE.replace(/\/$/, '')}${path.startsWith('/') ? path : `/${path}`}`
  const h = headers(rest.headers as Record<string, string>, omitContentType)
  return fetch(url, { ...rest, headers: { ...h, ...(rest.headers || {}) } })
}

export async function apiJson<T>(path: string, options?: RequestInit): Promise<T> {
  const r = await apiFetch(path, options)
  if (!r.ok) {
    const body = await r.text()
    let detail = body
    try {
      const j = JSON.parse(body)
      if (j.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch {
      // ignore
    }
    throw new ApiError(r.status, detail)
  }
  if (r.status === 204 || r.headers.get('content-length') === '0') return undefined as T
  return r.json() as Promise<T>
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

const UPLOAD_TIMEOUT_MS = 30_000

/** POST multipart form data (e.g. file upload). Do not set Content-Type. */
export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS)
  try {
    const r = await apiFetch(path, {
      method: 'POST',
      body: formData,
      omitContentType: true,
      signal: controller.signal,
    })
    if (!r.ok) {
      const body = await r.text()
      let detail = body
      try {
        const j = JSON.parse(body)
        if (j.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
      } catch {
        // ignore
      }
      throw new ApiError(r.status, detail)
    }
    return r.json() as Promise<T>
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new ApiError(0, `Request timed out. Is the API running at ${BASE}? Start it with: uvicorn apps.api.main:app --reload`)
    }
    if (err instanceof ApiError) throw err
    throw new ApiError(0, `Cannot reach the API at ${BASE}. Start the backend with: uvicorn apps.api.main:app --reload`)
  } finally {
    clearTimeout(timeoutId)
  }
}
