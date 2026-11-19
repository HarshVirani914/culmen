/** "1:00:00" | "90:30" | "45" -> seconds. Empty -> null, invalid -> NaN. */
export function parseTime(input: string): number | null {
  const s = input.trim()
  if (!s) return null
  const parts = s.split(':')
  if (parts.length > 3 || parts.some((p) => !/^\d+(\.\d+)?$/.test(p))) return NaN
  return parts.reduce((acc, p) => acc * 60 + Number(p), 0)
}

export function fmtTime(sec: number): string {
  const s = Math.floor(sec)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`
}

/** Hours, minutes, seconds text fields to seconds. All empty -> null, invalid -> NaN. */
export function hmsToSeconds(h: string, m: string, s: string): number | null {
  const parts = [h, m, s].map((p) => p.trim())
  if (parts.every((p) => p === '')) return null
  if (parts.some((p) => p !== '' && !/^\d+$/.test(p))) return NaN
  const [hh, mm, ss] = parts.map((p) => (p === '' ? 0 : Number(p)))
  if (mm > 59 || ss > 59) return NaN
  return hh * 3600 + mm * 60 + ss
}

export const MIN_RANGE_SECONDS = 20
export const MAX_RANGE_SECONDS = 3 * 3600

/** Human explanation of what is wrong with a start/end range, or null when it is fine. */
export function rangeProblem(start: number | null, end: number | null): string | null {
  if ((start !== null && Number.isNaN(start)) || (end !== null && Number.isNaN(end))) {
    return 'Enter a valid time (minutes and seconds go up to 59).'
  }
  if (start === null || end === null) return null
  if (end <= start) return 'The end must be after the start.'
  if (end - start < MIN_RANGE_SECONDS) return `Range is too short (${end - start} s). Check hours, minutes and seconds.`
  if (end - start > MAX_RANGE_SECONDS) return 'Max 3 hours per analysis.'
  return null
}
