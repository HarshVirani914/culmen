import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { getJob, getLive, jobVideoUrl, startLive, stopLive, type Job, type LiveSnapshot } from '@/lib/api'
import { sparklinePoints } from '@/lib/live'
import { fmtTime } from '@/lib/time'

const RUNNING = ['starting', 'recording']

export function LivePanel({ onOpen }: { onOpen: (job: Job) => void }) {
  const [url, setUrl] = useState('')
  const [notes, setNotes] = useState('')
  const [sid, setSid] = useState<string | null>(null)
  const [snap, setSnap] = useState<LiveSnapshot | null>(null)
  const [jobs, setJobs] = useState<Record<string, Job>>({})
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!sid) return
    let alive = true
    const tick = async () => {
      try {
        const s = await getLive(sid)
        if (!alive) return
        setSnap(s)
        for (const id of s.moments) {
          setJobs((prev) => (prev[id] ? prev : { ...prev, [id]: undefined as unknown as Job }))
        }
      } catch (e) {
        if (alive) toast.error((e as Error).message)
      }
    }
    tick()
    const t = window.setInterval(tick, 2000)
    return () => {
      alive = false
      window.clearInterval(t)
    }
  }, [sid])

  // Load (and refresh, titles arrive later) the job behind every moment card.
  useEffect(() => {
    if (!snap) return
    let alive = true
    Promise.all(snap.moments.map((id) => getJob(id).catch(() => null))).then((all) => {
      if (!alive) return
      setJobs(Object.fromEntries(all.filter((j): j is Job => !!j).map((j) => [j.id, j])))
    })
    return () => {
      alive = false
    }
  }, [snap?.moments.join(','), snap?.status])

  const running = snap ? RUNNING.includes(snap.status) : false
  const start = async () => {
    setBusy(true)
    try {
      const { id } = await startLive(url.trim(), notes.trim())
      setSid(id)
      setSnap(null)
      setJobs({})
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  const stop = async () => {
    if (!sid) return
    try {
      setSnap(await stopLive(sid))
    } catch (e) {
      toast.error((e as Error).message)
    }
  }
  const elapsed = snap ? (Date.now() / 1000 - snap.started_at) : 0
  const noChatNotice = snap && !snap.signals.chat && (!snap.signals.chat_source || elapsed > 90)

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Live clipping</CardTitle>
          <CardDescription>
            Records the stream into a small rolling buffer and saves moments when chat and audio spike. Works
            with YouTube, Twitch and Kick live streams.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          {!running && (
            <form
              className="grid gap-4"
              onSubmit={(e) => {
                e.preventDefault()
                if (url.trim()) start()
              }}
            >
              <div className="grid gap-2">
                <Label htmlFor="live-url">Live stream URL</Label>
                <Input id="live-url" placeholder="https://www.twitch.tv/…" value={url} onChange={(e) => setUrl(e.target.value)} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="live-notes">What to focus on (optional)</Label>
                <Textarea id="live-notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="e.g. clutch plays, rage moments" />
              </div>
              <div>
                <Button type="submit" disabled={busy || !url.trim()}>
                  {busy ? 'Connecting…' : 'Start live session'}
                </Button>
              </div>
            </form>
          )}
          {snap && (
            <div className="grid gap-3">
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant={running ? 'default' : 'secondary'}>{snap.status}</Badge>
                <span className="text-sm font-medium">{snap.title || snap.url}</span>
                <span className="text-muted-foreground ml-auto text-xs">
                  buffer {fmtTime(snap.buffer_seconds)} · disk {snap.disk_mb} MB · {snap.moments.length} moments
                </span>
              </div>
              <svg viewBox="0 0 300 40" className="bg-muted h-12 w-full rounded" preserveAspectRatio="none" role="img" aria-label="Live reaction score">
                <polyline fill="none" stroke="currentColor" strokeWidth="1.5" points={sparklinePoints(snap.recent_scores, 300, 36)} transform="translate(0 2)" />
              </svg>
              {noChatNotice && (
                <p className="text-muted-foreground text-xs">
                  Chat isn’t connected for this stream, so moments are detected from audio only.
                </p>
              )}
              {snap.error && <p className="text-destructive text-xs">{snap.error}</p>}
              {running && (
                <div>
                  <Button variant="outline" onClick={stop}>
                    Stop session
                  </Button>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {snap && (
        <div className="grid gap-4 sm:grid-cols-2">
          {snap.moments.length === 0 && (
            <p className="text-muted-foreground text-sm">No moments yet. They appear when chat and audio spike.</p>
          )}
          {[...snap.moments].reverse().map((id) => {
            const job = jobs[id]
            const c = job?.candidates[0]
            return (
              <Card key={id}>
                <CardContent className="grid gap-3 pt-6">
                  <video src={jobVideoUrl(id)} controls preload="metadata" className="aspect-video w-full rounded bg-black" />
                  <div>
                    <p className="font-medium">{c?.title ?? 'Moment'}</p>
                    {c?.hook && <p className="text-muted-foreground text-sm">{c.hook}</p>}
                    {c && <p className="text-muted-foreground text-xs">{Math.round(c.end - c.start)}s · score {(c.score * 100).toFixed(0)}</p>}
                  </div>
                  <Button size="sm" disabled={!job} onClick={() => job && onOpen(job)}>
                    Frame and render
                  </Button>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
