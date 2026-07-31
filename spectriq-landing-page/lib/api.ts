/**
 * API client for the Spectriq FastAPI backend.
 *
 * Auth is handled by Clerk. Every request carries the user's Clerk session
 * token as `Authorization: Bearer <token>`; the backend verifies that token
 * against Clerk's JWKS (see app/auth.py on the backend) rather than trusting
 * anything the client claims about its own identity.
 *
 * This module can't call Clerk's React hooks directly (it's plain
 * functions, not a component), so pages register a token-getter once via
 * `setTokenProvider` - see app/dashboard/page.tsx and app/results/page.tsx
 * for the `useAuth().getToken` wiring.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, '') || 'http://localhost:8000'

type TokenGetter = () => Promise<string | null>

let tokenGetter: TokenGetter | null = null

/** Called once per page (in a useEffect) with Clerk's `getToken` function. */
export function setTokenProvider(fn: TokenGetter) {
  tokenGetter = fn
}

async function authHeaders(): Promise<Record<string, string>> {
  const token = tokenGetter ? await tokenGetter() : null
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// ---------- shared types (mirrors app/schemas.py) ----------

export type JobStatus =
  | 'queued'
  | 'extracting'
  | 'transcribing'
  | 'summarizing'
  | 'indexing'
  | 'done'
  | 'failed'

export interface ActionItem {
  text: string
  assignee: string | null
}

export interface MeetingSummary {
  id: string
  title: string | null
  status: JobStatus
  created_at: string
  duration_seconds: number | null
}

export interface TranscriptSegment {
  start: number
  end: number
  text: string
}

export interface MeetingDetail {
  id: string
  title: string | null
  status: JobStatus
  original_filename: string
  duration_seconds: number | null
  transcript_segments: TranscriptSegment[] | null
  transcript_text: string | null
  summary: string | null
  key_decisions: string[] | null
  action_items: ActionItem[] | null
  open_questions: string[] | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface UploadResponse {
  meeting_id: string
  job_id: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatSource {
  chunk_text: string
  start_timestamp: number
}

export interface ChatResponse {
  response: string
  sources: ChatSource[]
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

async function extractErrorDetail(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (typeof data?.detail === 'string') return data.detail
    if (data?.detail) return JSON.stringify(data.detail)
  } catch {
    // response wasn't JSON - fall through
  }
  return `Request failed with status ${res.status}`
}

// ---------- Upload ----------

export async function uploadMeeting(
  file: File,
  onProgress?: (pct: number) => void
): Promise<UploadResponse> {
  // Uses XHR instead of fetch so we can report upload progress for large
  // audio/video files. Auth token is fetched up front (before opening the
  // XHR) since XHR itself has no async-friendly way to attach a header.
  const headers = await authHeaders()

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE_URL}/upload`)

    Object.entries(headers).forEach(([k, v]) => xhr.setRequestHeader(k, v))

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    }

    xhr.onload = () => {
      let body: any = null
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        // ignore parse errors, handled below
      }
      if (xhr.status >= 200 && xhr.status < 300 && body) {
        resolve(body as UploadResponse)
      } else {
        const detail =
          (body && typeof body.detail === 'string' && body.detail) ||
          `Upload failed with status ${xhr.status}`
        reject(new ApiError(xhr.status, detail))
      }
    }

    xhr.onerror = () => reject(new ApiError(0, 'Network error - is the backend running?'))

    const formData = new FormData()
    formData.append('file', file)
    xhr.send(formData)
  })
}

// ---------- Jobs ----------

export interface JobStatusResponse {
  job_id: string
  meeting_id: string
  status: JobStatus
  error_message: string | null
  updated_at: string
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/jobs/${jobId}/status`, {
    headers: await authHeaders(),
  })
  if (!res.ok) throw new ApiError(res.status, await extractErrorDetail(res))
  return res.json()
}

// ---------- Meetings ----------

export async function listMeetings(): Promise<MeetingSummary[]> {
  const res = await fetch(`${API_BASE_URL}/meetings`, {
    headers: await authHeaders(),
    cache: 'no-store',
  })
  if (!res.ok) throw new ApiError(res.status, await extractErrorDetail(res))
  const data = await res.json()
  return data.meetings
}

export async function getMeeting(meetingId: string): Promise<MeetingDetail> {
  const res = await fetch(`${API_BASE_URL}/meetings/${meetingId}`, {
    headers: await authHeaders(),
    cache: 'no-store',
  })
  if (!res.ok) throw new ApiError(res.status, await extractErrorDetail(res))
  return res.json()
}

export async function updateMeeting(
  meetingId: string,
  patch: { title?: string; transcript_text?: string }
): Promise<MeetingDetail> {
  const res = await fetch(`${API_BASE_URL}/meetings/${meetingId}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new ApiError(res.status, await extractErrorDetail(res))
  return res.json()
}

// ---------- Chat (RAG) ----------

export async function chatWithMeeting(
  meetingId: string,
  message: string,
  conversationHistory: ChatMessage[]
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE_URL}/meetings/${meetingId}/chat`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      conversation_history: conversationHistory,
      stream: false,
    }),
  })
  if (!res.ok) throw new ApiError(res.status, await extractErrorDetail(res))
  return res.json()
}

/**
 * Streaming variant - consumes the backend's SSE response
 * (`event: delta` / `event: done` / `event: error`) and calls back as
 * text arrives. Falls back gracefully if the stream errors mid-way.
 */
export async function chatWithMeetingStream(
  meetingId: string,
  message: string,
  conversationHistory: ChatMessage[],
  onDelta: (textSoFar: string, delta: string) => void
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE_URL}/meetings/${meetingId}/chat`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      conversation_history: conversationHistory,
      stream: true,
    }),
  })

  if (!res.ok || !res.body) {
    throw new ApiError(res.status, await extractErrorDetail(res))
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let fullText = ''
  let finalPayload: ChatResponse | null = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE events are separated by a blank line.
    const events = buffer.split('\n\n')
    buffer = events.pop() || ''

    for (const rawEvent of events) {
      const lines = rawEvent.split('\n')
      let eventType = 'message'
      let data = ''
      for (const line of lines) {
        if (line.startsWith('event:')) eventType = line.slice(6).trim()
        if (line.startsWith('data:')) data += line.slice(5).trim()
      }
      if (!data) continue

      if (eventType === 'delta') {
        const parsed = JSON.parse(data)
        fullText += parsed.text
        onDelta(fullText, parsed.text)
      } else if (eventType === 'done') {
        finalPayload = JSON.parse(data)
      } else if (eventType === 'error') {
        const parsed = JSON.parse(data)
        throw new ApiError(502, parsed.error || 'Chat generation failed')
      }
    }
  }

  return finalPayload || { response: fullText, sources: [] }
}
