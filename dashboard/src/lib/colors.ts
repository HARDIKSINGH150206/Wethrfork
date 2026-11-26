import type { Channel } from '../api/types'

type RGB = [number, number, number]
const lerp = (a: RGB, b: RGB, t: number): RGB => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]

function ramp(stops: RGB[], t: number): RGB {
  const x = Math.min(Math.max(t, 0), 1) * (stops.length - 1)
  const i = Math.min(Math.floor(x), stops.length - 2)
  return lerp(stops[i], stops[i + 1], x - i)
}

const WARM: RGB[] = [[49, 54, 149], [116, 173, 209], [254, 224, 144], [244, 109, 67], [165, 0, 38]]
const BLUE: RGB[] = [[247, 251, 255], [158, 202, 225], [66, 146, 198], [8, 81, 156], [8, 29, 88]]
const TEAL: RGB[] = [[255, 255, 217], [127, 205, 187], [44, 127, 184], [37, 52, 148]]
const DIV: RGB[] = [[33, 102, 172], [146, 197, 222], [247, 247, 247], [244, 165, 130], [178, 24, 43]]
const SEQ: RGB[] = [[68, 1, 84], [59, 82, 139], [33, 144, 140], [93, 200, 99], [253, 231, 37]]

export interface Scale { lo: number; hi: number; unit: string; diverging: boolean; color: (v: number) => RGB; convert: (v: number) => number }

export function scaleFor(ch: Channel, delta = false, deltaMax = 1): Scale {
  const id = (v: number) => v
  if (delta) {
    const unit = { t2m: 'K', tp: 'mm/day', u10: 'm/s', v10: 'm/s', msl: 'hPa', tcwv: 'kg/m²' }[ch]
    const conv = ch === 'msl' ? (v: number) => v / 100 : id
    const m = ch === 'msl' ? deltaMax / 100 : deltaMax
    return { lo: -m, hi: m, unit, diverging: true, color: (v) => ramp(DIV, 0.5 + (0.5 * v) / (m || 1)), convert: conv }
  }
  switch (ch) {
    case 't2m': return { lo: 0, hi: 45, unit: '°C', diverging: false, convert: (v) => v - 273.15, color: (v) => ramp(WARM, v / 45) }
    case 'tp': return { lo: 0, hi: 100, unit: 'mm/day', diverging: false, convert: id, color: (v) => ramp(BLUE, Math.sqrt(Math.max(v, 0) / 100)) }
    case 'u10': return { lo: -15, hi: 15, unit: 'm/s', diverging: true, convert: id, color: (v) => ramp(DIV, 0.5 + v / 30) }
    case 'v10': return { lo: -15, hi: 15, unit: 'm/s', diverging: true, convert: id, color: (v) => ramp(DIV, 0.5 + v / 30) }
    case 'msl': return { lo: 990, hi: 1025, unit: 'hPa', diverging: false, convert: (v) => v / 100, color: (v) => ramp(SEQ, (v - 990) / 35) }
    case 'tcwv': return { lo: 0, hi: 70, unit: 'kg/m²', diverging: false, convert: id, color: (v) => ramp(TEAL, v / 70) }
  }
}

/** 98th percentile of |x|, floored so an all-zero delta still has a scale. */
export function robustMax(x: Float32Array): number {
  const a = Array.from(x, Math.abs).sort((p, q) => p - q)
  return Math.max(a[Math.floor(a.length * 0.98)] ?? 0, 1e-6)
}
