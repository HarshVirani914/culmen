/** SVG polyline points for a sparkline of 0..1 scores inside a w x h box. */
export function sparklinePoints(scores: number[], w: number, h: number): string {
  if (scores.length === 0) return ''
  const lo = Math.min(...scores)
  const hi = Math.max(...scores)
  const span = hi - lo
  const stepX = scores.length > 1 ? w / (scores.length - 1) : 0
  return scores
    .map((v, i) => {
      const y = span > 1e-9 ? h - ((v - lo) / span) * h : h / 2
      return `${+(i * stepX).toFixed(2)},${+y.toFixed(2)}`
    })
    .join(' ')
}
