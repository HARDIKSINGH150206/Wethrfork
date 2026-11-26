import { CELLS } from './grid'
import { dayField, lerpInto } from './interp'
import type { Units } from './units'
import { pressLabel, pressOf, tempDelta, tempLabel, tempOf, windLabel, windOf } from './units'

export type LayerId = 'wind' | 'temp' | 'rain' | 'pressure' | 'moisture'
type RGBA = [number, number, number, number]
type Stop = [number, RGBA]

export interface LayerDef {
  id: LayerId
  label: string
  lo: number // SI range of the colour lookup
  hi: number
  warp: 'lin' | 'sqrt'
  stops: Stop[]
  ticks: number[] // SI values for the legend
  /** typical magnitude of a meaningful change, used as the floor of the delta scale (SI) */
  deltaFloor: number
  fmt: (si: number, u: Units, delta?: boolean) => string
  unit: (u: Units) => string
  /** convert an SI value to display units for legend ticks */
  disp: (si: number, u: Units) => number
}

const c = (r: number, g: number, b: number, a = 1): RGBA => [r, g, b, a]

// Palettes are in SI (K, m/s, mm/day, Pa, kg/m2); temperature stops are given in degrees C and shifted.
const T = (cc: number): number => cc + 273.15
export const LAYERS: Record<LayerId, LayerDef> = {
  wind: {
    id: 'wind', label: 'Wind', lo: 0, hi: 30, warp: 'lin', deltaFloor: 1,
    stops: [[0, c(40, 70, 160, 0.35)], [2, c(52, 118, 200, 0.55)], [5, c(66, 176, 170, 0.7)], [8, c(110, 205, 110, 0.78)], [12, c(240, 226, 80, 0.85)], [17, c(246, 150, 52, 0.9)], [23, c(220, 52, 44, 0.92)], [30, c(150, 20, 80, 0.95)]],
    ticks: [0, 3, 6, 10, 15, 20, 30],
    fmt: (v, u) => `${windOf(v, u.wind).toFixed(1)} ${windLabel(u.wind)}`, unit: (u) => windLabel(u.wind), disp: (v, u) => windOf(v, u.wind),
  },
  temp: {
    id: 'temp', label: 'Temperature', lo: T(-20), hi: T(50), warp: 'lin', deltaFloor: 0.5,
    stops: [[T(-20), c(120, 70, 190, 0.85)], [T(-8), c(60, 90, 210, 0.85)], [T(2), c(70, 165, 225, 0.85)], [T(12), c(90, 205, 160, 0.85)], [T(22), c(240, 230, 80, 0.88)], [T(31), c(246, 150, 52, 0.9)], [T(40), c(212, 52, 40, 0.92)], [T(50), c(120, 14, 50, 0.95)]],
    ticks: [T(-10), T(0), T(10), T(20), T(30), T(40)],
    fmt: (v, u, d) => `${(d ? tempDelta(v, u.temp) : tempOf(v, u.temp)).toFixed(1)} ${tempLabel(u.temp)}`, unit: (u) => tempLabel(u.temp), disp: (v, u) => tempOf(v, u.temp),
  },
  rain: {
    id: 'rain', label: 'Rain', lo: 0, hi: 100, warp: 'sqrt', deltaFloor: 1,
    stops: [[0, c(120, 200, 255, 0)], [0.4, c(120, 200, 255, 0.25)], [1.5, c(70, 190, 225, 0.6)], [5, c(60, 175, 110, 0.78)], [12, c(250, 225, 60, 0.86)], [30, c(250, 140, 40, 0.9)], [60, c(228, 56, 54, 0.93)], [100, c(150, 40, 170, 0.95)]],
    ticks: [0.5, 2, 5, 10, 25, 50, 100],
    fmt: (v) => `${v.toFixed(1)} mm/day`, unit: () => 'mm/day', disp: (v) => v,
  },
  pressure: {
    id: 'pressure', label: 'Pressure', lo: 98000, hi: 103500, warp: 'lin', deltaFloor: 100,
    stops: [[98000, c(110, 60, 180, 0.85)], [99200, c(60, 100, 210, 0.85)], [100000, c(70, 170, 220, 0.85)], [100800, c(110, 205, 140, 0.85)], [101400, c(240, 230, 100, 0.86)], [102200, c(246, 150, 60, 0.9)], [103500, c(210, 50, 44, 0.92)]],
    ticks: [98500, 99500, 100500, 101000, 101500, 102500],
    fmt: (v, u, d) => (d ? `${(pressOf(v, u.press)).toFixed(1)} ${pressLabel(u.press)}` : `${pressOf(v, u.press).toFixed(u.press === 'hPa' ? 1 : 0)} ${pressLabel(u.press)}`),
    unit: (u) => pressLabel(u.press), disp: (v, u) => pressOf(v, u.press),
  },
  moisture: {
    id: 'moisture', label: 'Moisture', lo: 0, hi: 75, warp: 'lin', deltaFloor: 1.5,
    stops: [[0, c(140, 210, 200, 0)], [10, c(140, 210, 200, 0.3)], [25, c(100, 190, 200, 0.6)], [40, c(58, 150, 220, 0.8)], [55, c(100, 80, 210, 0.88)], [65, c(190, 70, 190, 0.92)], [75, c(240, 60, 120, 0.95)]],
    ticks: [10, 20, 30, 40, 50, 60, 70],
    fmt: (v) => `${v.toFixed(1)} kg/m²`, unit: () => 'kg/m²', disp: (v) => v,
  },
}
export const LAYER_ORDER: LayerId[] = ['wind', 'temp', 'rain', 'pressure', 'moisture']

const N = 512
const lutCache = new Map<string, Uint8ClampedArray>()

function interpStops(stops: Stop[], x: number): RGBA {
  if (x <= stops[0][0]) return stops[0][1]
  for (let i = 1; i < stops.length; i++) {
    if (x <= stops[i][0]) {
      const [x0, a] = stops[i - 1], [x1, b] = stops[i]
      const t = (x - x0) / (x1 - x0 || 1)
      return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * t]
    }
  }
  return stops[stops.length - 1][1]
}

/** Colour lookup for a layer (absolute values). Index with `lutIndex`. */
export function lut(layer: LayerDef): Uint8ClampedArray {
  let l = lutCache.get(layer.id)
  if (l) return l
  l = new Uint8ClampedArray(N * 4)
  for (let k = 0; k < N; k++) {
    const t = k / (N - 1)
    const x = layer.warp === 'sqrt' ? layer.lo + (layer.hi - layer.lo) * t * t : layer.lo + (layer.hi - layer.lo) * t
    const [r, g, b, a] = interpStops(layer.stops, x)
    l[k * 4] = r; l[k * 4 + 1] = g; l[k * 4 + 2] = b; l[k * 4 + 3] = a * 255
  }
  lutCache.set(layer.id, l)
  return l
}
export function lutIndex(layer: LayerDef, v: number): number {
  const t = Math.min(Math.max((v - layer.lo) / (layer.hi - layer.lo), 0), 1)
  return Math.round((layer.warp === 'sqrt' ? Math.sqrt(t) : t) * (N - 1)) * 4
}

/** Symmetric diverging lookup for deltas: blue (negative) through transparent to red (positive). */
const DIV: Stop[] = [[-1, c(30, 90, 220, 0.95)], [-0.5, c(90, 160, 240, 0.8)], [-0.12, c(190, 220, 250, 0.25)], [0, c(255, 255, 255, 0)], [0.12, c(255, 215, 190, 0.25)], [0.5, c(245, 120, 90, 0.8)], [1, c(200, 20, 40, 0.95)]]
let divLut: Uint8ClampedArray | null = null
export function divergingLut(): Uint8ClampedArray {
  if (divLut) return divLut
  divLut = new Uint8ClampedArray(N * 4)
  for (let k = 0; k < N; k++) {
    const [r, g, b, a] = interpStops(DIV, (k / (N - 1)) * 2 - 1)
    divLut[k * 4] = r; divLut[k * 4 + 1] = g; divLut[k * 4 + 2] = b; divLut[k * 4 + 3] = a * 255
  }
  return divLut
}
export const divergingIndex = (v: number, dmax: number) => Math.round(((Math.min(Math.max(v / dmax, -1), 1) + 1) / 2) * (N - 1)) * 4

const tmpA = new Float32Array(CELLS)
const tmpB = new Float32Array(CELLS)

/** Scalar field of a layer at fractional day `tf` (0-based), linearly blended in time. Returns a shared buffer. */
export function scalarAt(roll: Float32Array, tf: number, id: LayerId, out: Float32Array = new Float32Array(CELLS)): Float32Array {
  const d0 = Math.min(Math.floor(tf), 9), d1 = Math.min(d0 + 1, 9), t = Math.min(Math.max(tf - d0, 0), 1)
  const get = (d: number, dst: Float32Array) => {
    if (id === 'wind') {
      const u = dayField(roll, d, 2), v = dayField(roll, d, 3)
      for (let i = 0; i < CELLS; i++) dst[i] = Math.hypot(u[i], v[i])
      return dst
    }
    const ch = { temp: 0, rain: 1, pressure: 4, moisture: 5 }[id]
    dst.set(dayField(roll, d, ch))
    return dst
  }
  get(d0, tmpA)
  if (d1 === d0 || t === 0) { out.set(tmpA); return out }
  get(d1, tmpB)
  return lerpInto(out, tmpA, tmpB, t)
}

/** Wind components at fractional day. */
export function windAt(roll: Float32Array, tf: number, u: Float32Array, v: Float32Array): void {
  const d0 = Math.min(Math.floor(tf), 9), d1 = Math.min(d0 + 1, 9), t = Math.min(Math.max(tf - d0, 0), 1)
  lerpInto(u, dayField(roll, d0, 2), dayField(roll, d1, 2), t)
  lerpInto(v, dayField(roll, d0, 3), dayField(roll, d1, 3), t)
}

/** Palette for the sensitivity overlay (values normalised to 0..1). */
export const SENS_LAYER: LayerDef = {
  id: 'wind', label: 'Sensitivity', lo: 0, hi: 1, warp: 'sqrt', deltaFloor: 1,
  stops: [[0, c(180, 80, 255, 0)], [0.1, c(180, 80, 255, 0.25)], [0.4, c(230, 80, 220, 0.6)], [0.7, c(255, 150, 90, 0.82)], [1, c(255, 240, 120, 0.95)]],
  ticks: [], fmt: (v) => v.toFixed(2), unit: () => '', disp: (v) => v,
}
