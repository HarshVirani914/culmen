import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

export type HMS = { h: string; m: string; s: string }
export const EMPTY_HMS: HMS = { h: '', m: '', s: '' }

const FIELDS: { key: keyof HMS; label: string; max: number | null }[] = [
  { key: 'h', label: 'hh', max: null },
  { key: 'm', label: 'mm', max: 59 },
  { key: 's', label: 'ss', max: 59 },
]

/** Three numeric fields (hours, minutes, seconds). Digits only; minutes and seconds are capped at 59. */
export function TimeInput({
  id,
  label,
  value,
  onChange,
  disabled,
  className,
}: {
  id: string
  label: string
  value: HMS
  onChange: (v: HMS) => void
  disabled?: boolean
  className?: string
}) {
  return (
    <div role="group" aria-label={label} className={cn('flex items-center gap-1', className)}>
      {FIELDS.map((f, i) => (
        <div key={f.key} className="flex items-center gap-1">
          {i > 0 && <span className="text-muted-foreground">:</span>}
          <Input
            id={i === 0 ? id : `${id}-${f.key}`}
            aria-label={`${label} ${f.label === 'hh' ? 'hours' : f.label === 'mm' ? 'minutes' : 'seconds'}`}
            className="w-16 text-center tabular-nums"
            inputMode="numeric"
            placeholder={f.label}
            maxLength={f.max === null ? 3 : 2}
            value={value[f.key]}
            disabled={disabled}
            onChange={(e) => {
              let v = e.target.value.replace(/\D/g, '')
              if (f.max !== null && v !== '' && Number(v) > f.max) v = String(f.max)
              onChange({ ...value, [f.key]: v })
            }}
          />
        </div>
      ))}
    </div>
  )
}
