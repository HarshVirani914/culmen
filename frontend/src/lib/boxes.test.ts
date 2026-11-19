import { describe, expect, it } from 'vitest'
import { dragToBox, moveBox, resizeBox, MIN_SIZE } from './boxes'

const rect = { w: 1000, h: 500 }

describe('dragToBox', () => {
  it('handles reverse drags with positive size', () => {
    const b = dragToBox({ x: 500, y: 250 }, { x: 100, y: 50 }, rect)
    expect(b.x).toBeCloseTo(0.1)
    expect(b.y).toBeCloseTo(0.1)
    expect(b.w).toBeCloseTo(0.4)
    expect(b.h).toBeCloseTo(0.4)
  })
  it('clamps past the frame edge', () => {
    const b = dragToBox({ x: 800, y: 400 }, { x: 2000, y: 900 }, rect)
    expect(b.x + b.w).toBeLessThanOrEqual(1)
    expect(b.y + b.h).toBeLessThanOrEqual(1)
  })
})

describe('moveBox', () => {
  it('cannot leave the frame', () => {
    const b = moveBox({ x: 0.5, y: 0.5, w: 0.4, h: 0.4 }, 5, -5)
    expect(b.x + b.w).toBeLessThanOrEqual(1)
    expect(b.y).toBeGreaterThanOrEqual(0)
  })
})

describe('resizeBox', () => {
  it('cannot go below min size', () => {
    const b = resizeBox({ x: 0.1, y: 0.1, w: 0.2, h: 0.2 }, 'se', -1, -1)
    expect(b.w).toBeGreaterThanOrEqual(MIN_SIZE)
    expect(b.h).toBeGreaterThanOrEqual(MIN_SIZE)
  })
  it('nw handle moves origin and keeps opposite corner fixed', () => {
    const b = resizeBox({ x: 0.2, y: 0.2, w: 0.4, h: 0.4 }, 'nw', -0.1, -0.1)
    expect(b.x).toBeCloseTo(0.1)
    expect(b.x + b.w).toBeCloseTo(0.6)
  })
})
