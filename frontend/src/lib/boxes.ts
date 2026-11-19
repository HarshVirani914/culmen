import type { Box } from './api'

export const MIN_SIZE = 0.02
export type Handle = 'nw' | 'ne' | 'sw' | 'se'

const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi)

/** Pixel drag inside a rect to a normalized, clamped box (order independent). */
export function dragToBox(
  a: { x: number; y: number },
  b: { x: number; y: number },
  rect: { w: number; h: number },
): Box {
  const x1 = clamp(Math.min(a.x, b.x) / rect.w, 0, 1)
  const x2 = clamp(Math.max(a.x, b.x) / rect.w, 0, 1)
  const y1 = clamp(Math.min(a.y, b.y) / rect.h, 0, 1)
  const y2 = clamp(Math.max(a.y, b.y) / rect.h, 0, 1)
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 }
}

/** dx/dy are normalized (fractions of the frame). */
export function moveBox(box: Box, dx: number, dy: number): Box {
  return {
    ...box,
    x: clamp(box.x + dx, 0, 1 - box.w),
    y: clamp(box.y + dy, 0, 1 - box.h),
  }
}

export function resizeBox(box: Box, handle: Handle, dx: number, dy: number): Box {
  let x1 = box.x
  let y1 = box.y
  let x2 = box.x + box.w
  let y2 = box.y + box.h
  if (handle.includes('w')) x1 = clamp(x1 + dx, 0, x2 - MIN_SIZE)
  else x2 = clamp(x2 + dx, x1 + MIN_SIZE, 1)
  if (handle.includes('n')) y1 = clamp(y1 + dy, 0, y2 - MIN_SIZE)
  else y2 = clamp(y2 + dy, y1 + MIN_SIZE, 1)
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 }
}
