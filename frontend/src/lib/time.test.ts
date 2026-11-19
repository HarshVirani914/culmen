import { describe, expect, it } from 'vitest'
import { fmtTime, parseTime } from './time'

describe('parseTime', () => {
  it('parses h:mm:ss, m:ss and plain seconds', () => {
    expect(parseTime('1:00:00')).toBe(3600)
    expect(parseTime('90:30')).toBe(5430)
    expect(parseTime(' 45 ')).toBe(45)
  })
  it('returns null for empty and NaN for invalid', () => {
    expect(parseTime('')).toBeNull()
    expect(parseTime('   ')).toBeNull()
    expect(parseTime('abc')).toBeNaN()
    expect(parseTime('1:xx')).toBeNaN()
    expect(parseTime('-5')).toBeNaN()
  })
})

describe('fmtTime', () => {
  it('formats with hours only when needed', () => {
    expect(fmtTime(65)).toBe('1:05')
    expect(fmtTime(3725)).toBe('1:02:05')
  })
})
