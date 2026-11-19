import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  deleteLibraryItem,
  libraryFileUrl,
  listLibrary,
  renameLibraryItem,
  type LibraryItem,
} from '@/lib/api'
import { fmtTime } from '@/lib/time'

const LAYOUT_NAMES: Record<string, string> = {
  stacked: 'Stacked',
  bubble: 'Facecam bubble',
  game_only: 'Gameplay only',
  face_only: 'Facecam only',
}

function Item({ item, onChanged }: { item: LibraryItem; onChanged: () => void }) {
  const [title, setTitle] = useState(item.title)
  useEffect(() => setTitle(item.title), [item.title])

  const rename = async () => {
    const t = title.trim()
    if (!t) return setTitle(item.title)
    if (t === item.title) return
    try {
      await renameLibraryItem(item.id, t)
      onChanged()
    } catch (e) {
      toast.error((e as Error).message)
      setTitle(item.title)
    }
  }
  const remove = async () => {
    if (!window.confirm(`Delete "${item.title}" from the library? This can't be undone.`)) return
    try {
      await deleteLibraryItem(item.id)
      toast.success('Deleted')
      onChanged()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  return (
    <Card>
      <CardContent className="grid gap-3 pt-6">
        <video
          src={libraryFileUrl(item.id)}
          controls
          preload="metadata"
          className="mx-auto aspect-[9/16] max-h-96 rounded-md bg-black"
        />
        <Input
          aria-label="Clip title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={rename}
          onKeyDown={(e) => e.key === 'Enter' && (e.currentTarget as HTMLInputElement).blur()}
        />
        <p className="text-muted-foreground text-xs">
          {item.channel && `${item.channel} · `}
          {fmtTime(item.stream_start)}–{fmtTime(item.stream_start + item.duration)} ·{' '}
          {Math.round(item.duration)}s · {LAYOUT_NAMES[item.layout] ?? item.layout} ·{' '}
          {(item.size_bytes / 1e6).toFixed(1)} MB · {new Date(item.created_at * 1000).toLocaleString()}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <a href={libraryFileUrl(item.id)} download>
            <Button size="sm">Download</Button>
          </a>
          {item.source_url && (
            <a href={item.source_url} target="_blank" rel="noreferrer" className="text-muted-foreground text-xs underline">
              Source
            </a>
          )}
          <Button size="sm" variant="outline" className="ml-auto" onClick={remove}>
            Delete
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function LibraryPanel({
  refreshKey,
  active,
  onCount,
}: {
  refreshKey: number
  active: boolean
  onCount: (n: number) => void
}) {
  const [items, setItems] = useState<LibraryItem[] | null>(null)
  const [n, setN] = useState(0)

  useEffect(() => {
    let alive = true
    listLibrary()
      .then((l) => {
        if (!alive) return
        setItems(l)
        onCount(l.length)
      })
      .catch((e) => alive && toast.error((e as Error).message))
    return () => {
      alive = false
    }
  }, [refreshKey, active, n])

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Library</CardTitle>
          <CardDescription>
            Clips you saved. They stay here after you refresh or close the app, and are never cleaned up automatically.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {items === null && <p className="text-muted-foreground text-sm">Loading…</p>}
          {items?.length === 0 && (
            <p className="text-muted-foreground text-sm">
              Nothing saved yet. Render a Short and press “Save to library”.
            </p>
          )}
        </CardContent>
      </Card>
      <div className="grid gap-4 sm:grid-cols-2">
        {items?.map((it) => <Item key={it.id} item={it} onChanged={() => setN((x) => x + 1)} />)}
      </div>
    </div>
  )
}
