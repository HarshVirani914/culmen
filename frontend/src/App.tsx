import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { BoxPicker } from '@/components/BoxPicker'
import { CandidateList } from '@/components/CandidateList'
import { LibraryPanel } from '@/components/LibraryPanel'
import { LivePanel } from '@/components/LivePanel'
import { RenderPanel } from '@/components/RenderPanel'
import { UrlForm } from '@/components/UrlForm'
import { Toaster } from '@/components/ui/sonner'
import { cn } from '@/lib/utils'
import { createJob, frameUrl, getJob, getProfile, saveProfile, type Box, type Job } from '@/lib/api'

const DEFAULT_GAME: Box = { x: 0, y: 0, w: 1, h: 1 }
const DEFAULT_FACE: Box = { x: 0.75, y: 0.05, w: 0.22, h: 0.3 }

export default function App() {
  const [tab, setTab] = useState<'replay' | 'live' | 'library'>('replay')
  const [libCount, setLibCount] = useState(0)
  const [libKey, setLibKey] = useState(0)
  const [job, setJob] = useState<Job | null>(null)
  const [game, setGame] = useState<Box>(DEFAULT_GAME)
  const [face, setFace] = useState<Box | null>(DEFAULT_FACE)
  const [saved, setSaved] = useState(false)
  const [selected, setSelected] = useState<number | null>(null)
  const [trims, setTrims] = useState<Record<number, [number, number]>>({})
  const [frameT, setFrameT] = useState<number | undefined>(undefined)

  const pending = job && job.status !== 'ready' && job.status !== 'error'

  useEffect(() => {
    if (!job || !pending) return
    const t = window.setInterval(async () => {
      try {
        setJob(await getJob(job.id))
      } catch (e) {
        toast.error((e as Error).message)
      }
    }, 2000)
    return () => window.clearInterval(t)
  }, [job?.id, pending])

  useEffect(() => {
    if (job?.status === 'error') toast.error(job.error ?? 'Analysis failed')
    if (job?.status === 'ready' && job.video) {
      getProfile(job.video.channel_id)
        .then((p) => {
          if (p) {
            setGame(p.game)
            setFace(p.face)
            setSaved(true)
          }
        })
        .catch(() => {})
      setSelected(job.candidates.length ? 0 : null)
      setTrims({})
    }
  }, [job?.status, job?.id])

  const start = async (url: string, notes: string, rs: number | null, re: number | null) => {
    try {
      const { id } = await createJob(url, notes, rs, re)
      setJob({ id, url, status: 'queued', error: null, candidates: [], video: null })
      setSaved(false)
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const clip =
    job?.status === 'ready' && selected !== null && job.candidates[selected]
      ? (() => {
          const c = job.candidates[selected]
          const [s, e] = trims[selected] ?? [c.start, c.end]
          return { start: s, end: e }
        })()
      : null

  // Frame the stream on a picture from the moment being rendered: overlays move between scenes.
  const clipMid = clip ? Math.round(((clip.start + clip.end) / 2) * 2) / 2 : undefined
  useEffect(() => {
    setFrameT(clipMid)
  }, [job?.id, selected, clipMid === undefined ? -1 : Math.floor((clip!.start + clip!.end) / 2 / 10)])

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Shorts Clipper</h1>
        <p className="text-muted-foreground text-sm">Turn stream highlights into vertical Shorts.</p>
      </header>
      <div role="tablist" className="bg-muted inline-flex rounded-lg p-1">
        {(['replay', 'live', 'library'] as const).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={cn(
              'rounded-md px-4 py-1.5 text-sm font-medium capitalize transition',
              tab === t ? 'bg-background shadow-sm' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {t}
            {t === 'library' && libCount > 0 && <span className="text-muted-foreground ml-1.5 text-xs">{libCount}</span>}
          </button>
        ))}
      </div>
      <div className={cn(tab !== 'replay' && 'hidden')}>
        <UrlForm status={job?.status ?? null} progress={job?.progress} onSubmit={start} />
      </div>
      <div className={cn(tab !== 'live' && 'hidden')}>
        <LivePanel
          onOpen={(j) => {
            setJob(j)
            setSaved(false)
          }}
        />
      </div>
      <div className={cn(tab !== 'library' && 'hidden')}>
        <LibraryPanel refreshKey={libKey} active={tab === 'library'} onCount={setLibCount} />
      </div>
      {job?.status === 'ready' && job.video && (
        <div className={cn('space-y-6', tab === 'library' && 'hidden')}>
          <CandidateList
            candidates={job.candidates}
            duration={job.video.duration}
            offset={job.video.offset ?? 0}
            selected={selected}
            trims={trims}
            onSelect={setSelected}
            onTrim={(i, r) => setTrims((t) => ({ ...t, [i]: r }))}
          />
          <BoxPicker
            src={frameUrl(job.id, frameT)}
            frameTime={frameT}
            clipStart={clip?.start ?? 0}
            clipEnd={clip?.end ?? job.video.duration}
            offset={job.video.offset ?? 0}
            onFrameTime={setFrameT}
            game={game}
            face={face}
            saved={saved}
            onChange={(g, f) => {
              setGame(g)
              setFace(f)
              setSaved(false)
            }}
            onSave={async () => {
              try {
                await saveProfile(job.video!.channel_id, { game, face })
                setSaved(true)
                toast.success(`Saved boxes for ${job.video!.channel || 'this streamer'}`)
              } catch (e) {
                toast.error((e as Error).message)
              }
            }}
          />
          <RenderPanel
            jobId={job.id}
            clip={clip}
            game={game}
            face={face}
            title={selected !== null ? job.candidates[selected]?.title : undefined}
            onSaved={() => setLibKey((k) => k + 1)}
          />
        </div>
      )}
      <Toaster />
    </div>
  )
}
