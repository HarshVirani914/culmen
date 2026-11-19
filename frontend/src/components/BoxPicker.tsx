import { useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import type { Box } from '@/lib/api'
import { moveBox, resizeBox, type Handle } from '@/lib/boxes'
import { cn } from '@/lib/utils'

const HANDLES: Handle[] = ['nw', 'ne', 'sw', 'se']
const HANDLE_POS: Record<Handle, string> = {
  nw: '-left-1.5 -top-1.5 cursor-nwse-resize',
  ne: '-right-1.5 -top-1.5 cursor-nesw-resize',
  sw: '-left-1.5 -bottom-1.5 cursor-nesw-resize',
  se: '-right-1.5 -bottom-1.5 cursor-nwse-resize',
}

function DraggableBox({
  box,
  label,
  color,
  frameRef,
  onChange,
}: {
  box: Box
  label: string
  color: string
  frameRef: React.RefObject<HTMLDivElement | null>
  onChange: (b: Box) => void
}) {
  const drag = useRef<{ x: number; y: number; box: Box; handle: Handle | null } | null>(null)

  const start = (e: React.PointerEvent, handle: Handle | null) => {
    e.stopPropagation()
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    drag.current = { x: e.clientX, y: e.clientY, box, handle }
  }
  const move = (e: React.PointerEvent) => {
    const d = drag.current
    const rect = frameRef.current?.getBoundingClientRect()
    if (!d || !rect) return
    const dx = (e.clientX - d.x) / rect.width
    const dy = (e.clientY - d.y) / rect.height
    onChange(d.handle ? resizeBox(d.box, d.handle, dx, dy) : moveBox(d.box, dx, dy))
  }
  const end = () => {
    drag.current = null
  }

  return (
    <div
      className={cn('absolute cursor-move border-2 touch-none', color)}
      style={{
        left: `${box.x * 100}%`,
        top: `${box.y * 100}%`,
        width: `${box.w * 100}%`,
        height: `${box.h * 100}%`,
      }}
      onPointerDown={(e) => start(e, null)}
      onPointerMove={move}
      onPointerUp={end}
    >
      <span className="absolute left-0 top-0 bg-black/70 px-1.5 py-0.5 text-xs text-white">{label}</span>
      {HANDLES.map((h) => (
        <div
          key={h}
          className={cn('absolute size-3 rounded-sm border border-white bg-current', HANDLE_POS[h])}
          onPointerDown={(e) => start(e, h)}
          onPointerMove={move}
          onPointerUp={end}
        />
      ))}
    </div>
  )
}

export function BoxPicker({
  src,
  game,
  face,
  onChange,
  onSave,
  saved,
}: {
  src: string
  game: Box
  face: Box | null
  onChange: (game: Box, face: Box | null) => void
  onSave: () => void
  saved: boolean
}) {
  const frameRef = useRef<HTMLDivElement>(null)
  return (
    <Card>
      <CardHeader>
        <CardTitle>2. Frame the stream</CardTitle>
        <CardDescription>
          Drag and resize the boxes: blue is the gameplay area, orange is the facecam. Saved per streamer.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div ref={frameRef} className="relative w-full select-none overflow-hidden rounded-md bg-black">
          <img src={src} alt="Sample frame" className="block w-full" draggable={false} />
          <DraggableBox
            box={game}
            label="Gameplay"
            color="border-blue-500 text-blue-500"
            frameRef={frameRef}
            onChange={(b) => onChange(b, face)}
          />
          {face && (
            <DraggableBox
              box={face}
              label="Facecam"
              color="border-orange-500 text-orange-500"
              frameRef={frameRef}
              onChange={(b) => onChange(game, b)}
            />
          )}
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Switch
              id="has-face"
              checked={face !== null}
              onCheckedChange={(on) =>
                onChange(game, on ? { x: 0.75, y: 0.05, w: 0.22, h: 0.3 } : null)
              }
            />
            <Label htmlFor="has-face">This streamer has a facecam</Label>
          </div>
          <Button variant="outline" onClick={onSave}>
            Save for this streamer
          </Button>
          {saved && <span className="text-muted-foreground text-xs">Saved</span>}
        </div>
      </CardContent>
    </Card>
  )
}
