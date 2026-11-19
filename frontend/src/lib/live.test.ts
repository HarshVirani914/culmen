import { describe, expect, it } from 'vitest'
import { sparklinePoints } from './live'

const nums = (s: string) => s.split(/[ ,]+/).filter(Boolean).map(Number)

describe('sparklinePoints', () => {
  it('returns empty string for no data', () => {
    expect(sparklinePoints([], 100, 20)).toBe('')
  })
  it('draws a flat line for constant or single values, never NaN', () => {
    for (const input of [[0.5], [0.5, 0.5, 0.5], [0, 0]]) {
      const out = sparklinePoints(input, 100, 20)
      expect(out).not.toContain('NaN')
      const ys = nums(out).filter((_, i) => i % 2 === 1)
      expect(new Set(ys).size).toBe(1)
    }
  })
  it('scales values into the box with high values drawn higher (smaller y)', () => {
    const pts = nums(sparklinePoints([0, 1, 0.5], 100, 20))
    const [x0, y0, x1, y1, x2, y2] = pts
    expect(x0).toBe(0)
    expect(x2).toBe(100)
    expect(y1).toBeLessThan(y0)
    expect(y1).toBeLessThan(y2)
    expect(Math.min(...pts.filter((_, i) => i % 2 === 1))).toBeGreaterThanOrEqual(0)
    expect(Math.max(...pts.filter((_, i) => i % 2 === 1))).toBeLessThanOrEqual(20)
    expect(x1).toBe(50)
  })
})
