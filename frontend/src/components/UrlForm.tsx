import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Textarea } from '@/components/ui/textarea'
import type { JobStatus } from '@/lib/api'
import { parseTime } from '@/lib/time'

const STATUS_TEXT: Record<string, string> = {
  queued: 'Queued…',
  downloading: 'Downloading video…',
  analyzing: 'Finding the best moments…',
}

export function UrlForm({
  status,
  onSubmit,
}: {
  status: JobStatus | null
  onSubmit: (url: string, notes: string, rangeStart: number | null, rangeEnd: number | null) => void
}) {
  const [url, setUrl] = useState('')
  const [notes, setNotes] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const rs = parseTime(from)
  const re = parseTime(to)
  const rangeError =
    Number.isNaN(rs) || Number.isNaN(re)
      ? 'Use h:mm:ss, m:ss or seconds'
      : rs !== null && re !== null && re <= rs
        ? 'End must be after start'
        : rs !== null && re !== null && re - rs > 3 * 3600
          ? 'Max 3 hours per analysis'
          : null
  const busy = status !== null && status !== 'ready' && status !== 'error'

  return (
    <Card>
      <CardHeader>
        <CardTitle>1. Stream link</CardTitle>
        <CardDescription>Paste a YouTube stream or replay URL. Moments are found automatically.</CardDescription>
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
            <Label htmlFor="url">YouTube URL</Label>
            <Input
              id="url"
              placeholder="https://www.youtube.com/watch?v=…"
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
            <div className="flex items-center gap-2">
              <Input placeholder="From, e.g. 1:00:00" value={from} onChange={(e) => setFrom(e.target.value)} disabled={busy} />
              <span className="text-muted-foreground">to</span>
              <Input placeholder="To, e.g. 2:00:00" value={to} onChange={(e) => setTo(e.target.value)} disabled={busy} />
            </div>
            {rangeError && <p className="text-destructive text-xs">{rangeError}</p>}
            <p className="text-muted-foreground text-xs">Only this section is downloaded. Videos over 3 hours need a range.</p>
          </div>
          <div className="flex items-center gap-4">
            <Button type="submit" disabled={busy || !url.trim() || !!rangeError}>
              {busy ? 'Analyzing…' : 'Analyze'}
            </Button>
            {busy && (
              <div className="flex-1 space-y-1">
                <Progress value={status === 'analyzing' ? 70 : 30} />
                <p className="text-muted-foreground text-xs">{STATUS_TEXT[status!]}</p>
              </div>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
