import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { BoxPicker } from '@/components/BoxPicker'
import { CandidateList } from '@/components/CandidateList'
import { RenderPanel } from '@/components/RenderPanel'
import { UrlForm } from '@/components/UrlForm'
import { Toaster } from '@/components/ui/sonner'
import { createJob, frameUrl, getJob, getProfile, saveProfile, type Box, type Job } from '@/lib/api'

const DEFAULT_GAME: Box = { x: 0, y: 0, w: 1, h: 1 }
const DEFAULT_FACE: Box = { x: 0.75, y: 0.05, w: 0.22, h: 0.3 }

export default function App() {
  const [job, setJob] = useState<Job | null>(null)
  const [game, setGame] = useState<Box>(DEFAULT_GAME)
  const [face, setFace] = useState<Box | null>(DEFAULT_FACE)
  const [saved, setSaved] = useState(false)
  const [selected, setSelected] = useState<number | null>(null)
  const [trims, setTrims] = useState<Record<number, [number, number]>>({})

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

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Shorts Clipper</h1>
        <p className="text-muted-foreground text-sm">Turn stream highlights into vertical Shorts.</p>
      </header>
      <UrlForm status={job?.status ?? null} progress={job?.progress} onSubmit={start} />
      {job?.status === 'ready' && job.video && (
        <>
          <BoxPicker
            src={frameUrl(job.id)}
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
          <CandidateList
            candidates={job.candidates}
            duration={job.video.duration}
            offset={job.video.offset ?? 0}
            selected={selected}
            trims={trims}
            onSelect={setSelected}
            onTrim={(i, r) => setTrims((t) => ({ ...t, [i]: r }))}
          />
          <RenderPanel jobId={job.id} clip={clip} game={game} face={face} />
        </>
      )}
      <Toaster />
    </div>
  )
}
