export type Layout = 'stacked' | 'bubble' | 'game_only' | 'face_only'
export type Box = { x: number; y: number; w: number; h: number }
export type Candidate = {
  start: number
  end: number
  score: number
  title: string
  hook: string
  llm_score?: number | null
}
export type VideoMeta = {
  title: string
  channel_id: string
  channel: string
  width: number
  height: number
  duration: number
  offset: number
}
export type JobStatus = 'queued' | 'downloading' | 'analyzing' | 'ready' | 'error'
export type JobProgress = { step: 'transcribing' | 'ranking'; done: number; total: number }
export type Job = {
  id: string
  url: string
  status: JobStatus
  error: string | null
  candidates: Candidate[]
  video: VideoMeta | null
  progress?: JobProgress | null
}
export type Profile = { game: Box; face: Box | null }
export type RenderState = {
  id: string
  status: 'queued' | 'rendering' | 'done' | 'error'
  error: string | null
  url: string | null
}
export type RenderRequest = {
  start: number
  end: number
  layout: Layout
  game: Box
  face: Box | null
  captions: boolean
  credit: boolean
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!r.ok) {
    let detail = r.statusText
    try {
      const j = await r.json()
      detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch {
      /* keep statusText */
    }
    throw new Error(detail)
  }
  return r.json() as Promise<T>
}

export const createJob = (url: string, notes: string, rangeStart?: number | null, rangeEnd?: number | null) =>
  req<{ id: string }>('/api/jobs', {
    method: 'POST',
    body: JSON.stringify({ url, notes, range_start: rangeStart ?? null, range_end: rangeEnd ?? null }),
  })
export const getJob = (id: string) => req<Job>(`/api/jobs/${id}`)
export const frameUrl = (id: string, t?: number) =>
  t === undefined ? `/api/jobs/${id}/frame` : `/api/jobs/${id}/frame?t=${t.toFixed(1)}`
export const getProfile = (channelId: string) =>
  req<Profile | null>(`/api/profiles/${encodeURIComponent(channelId)}`)
export const saveProfile = (channelId: string, p: Profile) =>
  req<{ ok: boolean }>(`/api/profiles/${encodeURIComponent(channelId)}`, {
    method: 'PUT',
    body: JSON.stringify(p),
  })
export const startRender = (jobId: string, r: RenderRequest) =>
  req<{ render_id: string }>(`/api/jobs/${jobId}/render`, { method: 'POST', body: JSON.stringify(r) })
export const getRender = (id: string) => req<RenderState>(`/api/renders/${id}`)
export const getHealth = () =>
  req<{ ok: boolean; ffmpeg: boolean; captions: boolean; llm: boolean }>('/api/health')

export type LiveStatus = 'starting' | 'recording' | 'ended' | 'error' | 'stopped'
export type LiveSnapshot = {
  id: string
  status: LiveStatus
  started_at: number
  url: string
  title: string
  buffer_seconds: number
  disk_mb: number
  sensitivity: Sensitivity
  signals: { chat: boolean; chat_source: boolean; audio: boolean }
  recent_scores: number[]
  moments: string[]
  error: string | null
}
export type Sensitivity = 'low' | 'normal' | 'high'
export const startLive = (url: string, notes: string, sensitivity: Sensitivity = 'normal') =>
  req<{ id: string }>('/api/live', { method: 'POST', body: JSON.stringify({ url, notes, sensitivity }) })
export const getLive = (id: string) => req<LiveSnapshot>(`/api/live/${id}`)
export const stopLive = (id: string) => req<LiveSnapshot>(`/api/live/${id}/stop`, { method: 'POST' })
export const jobVideoUrl = (id: string) => `/api/jobs/${id}/video`

export type LibraryItem = {
  id: string
  title: string
  created_at: number
  render_id: string
  job_id: string
  source_url: string
  stream_title: string
  channel: string
  layout: Layout | ''
  captions: boolean
  credit: boolean
  clip_start: number
  clip_end: number
  stream_start: number
  duration: number
  size_bytes: number
}
export const saveToLibrary = (renderId: string, title?: string) =>
  req<{ id: string }>('/api/library', { method: 'POST', body: JSON.stringify({ render_id: renderId, title }) })
export const listLibrary = () => req<LibraryItem[]>('/api/library')
export const renameLibraryItem = (id: string, title: string) =>
  req<{ ok: boolean }>(`/api/library/${id}`, { method: 'PATCH', body: JSON.stringify({ title }) })
export const deleteLibraryItem = (id: string) => req<{ ok: boolean }>(`/api/library/${id}`, { method: 'DELETE' })
export const libraryFileUrl = (id: string) => `/api/library/${id}/file`
