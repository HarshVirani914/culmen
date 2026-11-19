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
}
export type JobStatus = 'queued' | 'downloading' | 'analyzing' | 'ready' | 'error'
export type Job = {
  id: string
  url: string
  status: JobStatus
  error: string | null
  candidates: Candidate[]
  video: VideoMeta | null
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

export const createJob = (url: string, notes: string) =>
  req<{ id: string }>('/api/jobs', { method: 'POST', body: JSON.stringify({ url, notes }) })
export const getJob = (id: string) => req<Job>(`/api/jobs/${id}`)
export const frameUrl = (id: string) => `/api/jobs/${id}/frame`
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
