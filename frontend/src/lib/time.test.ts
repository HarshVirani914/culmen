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

import { hmsToSeconds, rangeProblem } from './time'

describe('hmsToSeconds', () => {
  it('combines hours, minutes and seconds', () => {
    expect(hmsToSeconds('1', '0', '0')).toBe(3600)
    expect(hmsToSeconds('2', '30', '15')).toBe(9015)
    expect(hmsToSeconds('', '5', '')).toBe(300)
  })
  it('returns null when every part is empty', () => {
    expect(hmsToSeconds('', '', '')).toBeNull()
    expect(hmsToSeconds(' ', '', ' ')).toBeNull()
  })
  it('returns NaN for invalid parts and out-of-range minutes or seconds', () => {
    expect(hmsToSeconds('a', '', '')).toBeNaN()
    expect(hmsToSeconds('1', '60', '0')).toBeNaN()
    expect(hmsToSeconds('1', '0', '75')).toBeNaN()
    expect(hmsToSeconds('-1', '0', '0')).toBeNaN()
  })
})

describe('rangeProblem', () => {
  it('accepts an empty range or a sensible one', () => {
    expect(rangeProblem(null, null)).toBeNull()
    expect(rangeProblem(3600, 7200)).toBeNull()
    expect(rangeProblem(3600, null)).toBeNull()
  })
  it('explains too short, reversed and too long ranges', () => {
    expect(rangeProblem(1, 2)).toMatch(/too short/i)
    expect(rangeProblem(7200, 3600)).toMatch(/after/i)
    expect(rangeProblem(0, 4 * 3600)).toMatch(/3 hours/)
  })
  it('flags invalid values', () => {
    expect(rangeProblem(NaN, 100)).toMatch(/valid/i)
  })
})
