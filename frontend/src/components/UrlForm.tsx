import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Textarea } from '@/components/ui/textarea'
import type { JobProgress, JobStatus } from '@/lib/api'
import { fmtTime, hmsToSeconds, rangeProblem } from '@/lib/time'
import { EMPTY_HMS, TimeInput, type HMS } from '@/components/TimeInput'

const STATUS_TEXT: Record<string, string> = {
  queued: 'Queued…',
  downloading: 'Downloading video…',
  analyzing: 'Finding the best moments…',
}

export function UrlForm({
  status,
  progress,
  onSubmit,
}: {
  status: JobStatus | null
  progress?: JobProgress | null
  onSubmit: (url: string, notes: string, rangeStart: number | null, rangeEnd: number | null) => void
}) {
  const [url, setUrl] = useState('')
  const [notes, setNotes] = useState('')
  const [from, setFrom] = useState<HMS>(EMPTY_HMS)
  const [to, setTo] = useState<HMS>(EMPTY_HMS)
  const rs = hmsToSeconds(from.h, from.m, from.s)
  const re = hmsToSeconds(to.h, to.m, to.s)
  const rangeError = rangeProblem(rs, re)
  const busy = status !== null && status !== 'ready' && status !== 'error'

  return (
    <Card>
      <CardHeader>
        <CardTitle>1. Stream link</CardTitle>
        <CardDescription>Paste a stream or replay link. Moments are found automatically.</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (url.trim() && !rangeError) onSubmit(url.trim(), notes.trim(), rs, re)
          }}
        >
          <div className="grid gap-2">
            <Label htmlFor="url">Video or stream URL (YouTube, Twitch, Kick)</Label>
            <Input
              id="url"
              placeholder="https://www.youtube.com/watch?v=… or twitch.tv/videos/…"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={busy}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="notes">What to focus on (optional)</Label>
            <Textarea
              id="notes"
              placeholder="e.g. clutch plays, rage moments, funny fails"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              disabled={busy}
            />
          </div>
          <div className="grid gap-2">
            <Label>Time range (optional, recommended for long streams)</Label>
            <div className="flex flex-wrap items-center gap-3">
              <TimeInput id="range-from" label="From" value={from} onChange={setFrom} disabled={busy} />
              <span className="text-muted-foreground">to</span>
              <TimeInput id="range-to" label="To" value={to} onChange={setTo} disabled={busy} />
              {[from.h, from.m, from.s, to.h, to.m, to.s].some(Boolean) && (
                <button
                  type="button"
                  className="text-muted-foreground text-xs underline"
                  onClick={() => {
                    setFrom(EMPTY_HMS)
                    setTo(EMPTY_HMS)
                  }}
                >
                  Clear
                </button>
              )}
            </div>
            {rangeError ? (
              <p className="text-destructive text-xs">{rangeError}</p>
            ) : (
              <p className="text-muted-foreground text-xs">
                {rs !== null && re !== null
                  ? `Analyzes ${fmtTime(rs)} to ${fmtTime(re)} (${fmtTime(re - rs)} long).`
                  : 'Hours, minutes, seconds. Only this section is downloaded. Videos over 4 hours need a range.'}
              </p>
            )}
          </div>
          <div className="flex items-center gap-4">
            <Button type="submit" disabled={busy || !url.trim() || !!rangeError}>
              {busy ? 'Analyzing…' : 'Analyze'}
            </Button>
            {busy && (
              <div className="flex-1 space-y-1">
                <Progress value={progress ? 50 + (50 * progress.done) / Math.max(progress.total, 1) : status === 'analyzing' ? 45 : 20} />
                <p className="text-muted-foreground text-xs">
                  {progress
                    ? progress.step === 'transcribing'
                      ? `Transcribing moments ${Math.min(progress.done + 1, progress.total)} of ${progress.total}…`
                      : 'Asking the LLM to rank moments…'
                    : STATUS_TEXT[status!]}
                </p>
              </div>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
