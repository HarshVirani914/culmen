import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Slider } from '@/components/ui/slider'
import type { Candidate } from '@/lib/api'
import { fmtTime as fmt } from '@/lib/time'
import { cn } from '@/lib/utils'


export function CandidateList({
  candidates,
  duration,
  offset,
  selected,
  trims,
  onSelect,
  onTrim,
}: {
  candidates: Candidate[]
  duration: number
  offset: number
  selected: number | null
  trims: Record<number, [number, number]>
  onSelect: (i: number) => void
  onTrim: (i: number, range: [number, number]) => void
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>3. Pick a moment</CardTitle>
        <CardDescription>Ranked by chat, audio and replay-graph reactions. Trim before rendering.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {candidates.length === 0 && (
          <p className="text-muted-foreground text-sm">
            No standout moments found in this video. Try another stream or one with a replay graph.
          </p>
        )}
        {candidates.map((c, i) => {
          const [s, e] = trims[i] ?? [c.start, c.end]
          const lo = Math.max(0, c.start - 15)
          const hi = Math.min(duration, c.end + 15)
          return (
            <div
              key={i}
              onClick={() => onSelect(i)}
              className={cn(
                'cursor-pointer rounded-lg border p-3 transition',
                selected === i ? 'border-primary ring-primary/30 ring-2' : 'hover:bg-muted/50',
              )}
            >
              <div className="flex items-center gap-2">
                <Badge variant="secondary">#{i + 1}</Badge>
                <span className="font-medium">{c.title}</span>
                <span className="text-muted-foreground ml-auto text-xs">
                  {fmt(s + offset)} – {fmt(e + offset)} · {Math.round(e - s)}s · score {(c.score * 100).toFixed(0)}
                </span>
              </div>
              {c.hook && <p className="text-muted-foreground mt-1 text-sm">{c.hook}</p>}
              {selected === i && (
                <div className="mt-4 px-1" onClick={(ev) => ev.stopPropagation()}>
                  <Slider
                    min={lo}
                    max={hi}
                    step={0.5}
                    minStepsBetweenValues={2}
                    value={[s, e]}
                    onValueChange={(v) => Array.isArray(v) && onTrim(i, [v[0], v[1]])}
                  />
                </div>
              )}
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
