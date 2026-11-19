import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { getRender, startRender, type Box, type Layout, type RenderState } from '@/lib/api'

const LAYOUT_LABELS: Record<Layout, string> = {
  stacked: 'Stacked',
  bubble: 'Facecam bubble',
  game_only: 'Gameplay only',
  face_only: 'Facecam only',
}

function Diagram({ layout }: { layout: Layout }) {
  const frame = 'relative h-28 w-16 overflow-hidden rounded border bg-muted'
  const face = 'bg-orange-400/70'
  const game = 'bg-blue-400/70'
  return (
    <div className={frame}>
      {layout === 'stacked' && (
        <>
          <div className={`absolute inset-x-0 top-0 h-[36%] ${face}`} />
          <div className={`absolute inset-x-0 bottom-0 h-[64%] ${game}`} />
        </>
      )}
      {layout === 'bubble' && (
        <>
          <div className={`absolute inset-0 ${game}`} />
          <div className={`absolute bottom-3 left-1 size-6 ${face}`} />
        </>
      )}
      {layout === 'game_only' && <div className={`absolute inset-x-0 top-[32%] h-[36%] ${game}`} />}
      {layout === 'face_only' && <div className={`absolute inset-0 ${face}`} />}
    </div>
  )
}

export function RenderPanel({
  jobId,
  clip,
  game,
  face,
}: {
  jobId: string
  clip: { start: number; end: number } | null
  game: Box
  face: Box | null
}) {
  const [layout, setLayout] = useState<Layout>('stacked')
  const [captions, setCaptions] = useState(true)
  const [credit, setCredit] = useState(true)
  const [render, setRender] = useState<RenderState | null>(null)
  const [busy, setBusy] = useState(false)
  const timer = useRef<number | null>(null)

  useEffect(() => () => {
    if (timer.current) window.clearInterval(timer.current)
  }, [])

  const needsFace = layout !== 'game_only'
  const blocked = !clip || (needsFace && !face)

  const run = async () => {
    if (!clip) return
    setBusy(true)
    setRender(null)
    try {
      const { render_id } = await startRender(jobId, {
        start: clip.start,
        end: clip.end,
        layout,
        game,
        face,
        captions,
        credit,
      })
      timer.current = window.setInterval(async () => {
        try {
          const r = await getRender(render_id)
          setRender(r)
          if (r.status === 'done' || r.status === 'error') {
            if (timer.current) window.clearInterval(timer.current)
            setBusy(false)
            if (r.status === 'error') toast.error(r.error ?? 'Render failed')
          }
        } catch (e) {
          if (timer.current) window.clearInterval(timer.current)
          setBusy(false)
          toast.error((e as Error).message)
        }
      }, 1500)
    } catch (e) {
      setBusy(false)
      toast.error((e as Error).message)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>4. Layout and render</CardTitle>
        <CardDescription>1080×1920 MP4, ready for Shorts.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-5">
        <Tabs value={layout} onValueChange={(v) => setLayout(v as Layout)}>
          <TabsList className="h-auto flex-wrap">
            {(Object.keys(LAYOUT_LABELS) as Layout[]).map((l) => (
              <TabsTrigger key={l} value={l} className="flex-col gap-2 p-2">
                <Diagram layout={l} />
                <span className="text-xs">{LAYOUT_LABELS[l]}</span>
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="flex flex-wrap gap-6">
          <div className="flex items-center gap-2">
            <Switch id="captions" checked={captions} onCheckedChange={setCaptions} />
            <Label htmlFor="captions">Captions (needs transcription, slower)</Label>
          </div>
          <div className="flex items-center gap-2">
            <Switch id="credit" checked={credit} onCheckedChange={setCredit} />
            <Label htmlFor="credit">Source credit line</Label>
          </div>
        </div>
        {needsFace && !face && (
          <p className="text-destructive text-sm">This layout needs a facecam box. Turn it on in step 2.</p>
        )}
        <div>
          <Button onClick={run} disabled={busy || blocked}>
            {busy ? 'Rendering…' : clip ? 'Render Short' : 'Pick a moment first'}
          </Button>
        </div>
        {busy && <Progress value={render?.status === 'rendering' ? 60 : 20} />}
        {render?.status === 'done' && render.url && (
          <div className="grid max-w-xs gap-3">
            <video src={render.url} controls className="aspect-[9/16] w-full rounded-md bg-black" />
            <a href={render.url} download="short.mp4">
              <Button variant="outline" className="w-full">
                Download MP4
              </Button>
            </a>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
