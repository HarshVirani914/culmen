import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Textarea } from '@/components/ui/textarea'
import type { JobStatus } from '@/lib/api'

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
  onSubmit: (url: string, notes: string) => void
}) {
  const [url, setUrl] = useState('')
  const [notes, setNotes] = useState('')
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
            if (url.trim()) onSubmit(url.trim(), notes.trim())
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
          <div className="flex items-center gap-4">
            <Button type="submit" disabled={busy || !url.trim()}>
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
