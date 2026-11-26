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
    stops: [[0, c(98, 113, 183, 0.92)], [1, c(57, 97, 159, 0.92)], [3, c(74, 148, 169, 0.92)], [5, c(77, 141, 123, 0.92)], [7, c(83, 165, 83, 0.92)], [9, c(53, 159, 53, 0.92)], [11, c(167, 157, 81, 0.92)], [13, c(159, 127, 58, 0.92)], [15, c(161, 108, 92, 0.92)], [17, c(129, 58, 78, 0.92)], [19, c(175, 80, 136, 0.92)], [21, c(117, 74, 147, 0.92)], [24, c(109, 97, 163, 0.92)], [27, c(68, 105, 141, 0.92)], [30, c(92, 144, 152, 0.92)]],
    ticks: [0, 2, 4, 6, 8, 10, 13, 16, 20, 25, 30],
    fmt: (v, u) => `${windOf(v, u.wind).toFixed(1)} ${windLabel(u.wind)}`, unit: (u) => windLabel(u.wind), disp: (v, u) => windOf(v, u.wind),
  },
  temp: {
    id: 'temp', label: 'Temperature', lo: T(-20), hi: T(50), warp: 'lin', deltaFloor: 0.5,
    stops: [[T(-20), c(115, 70, 160, 0.92)], [T(-10), c(68, 92, 180, 0.92)], [T(0), c(80, 150, 200, 0.92)], [T(8), c(82, 175, 175, 0.92)], [T(14), c(90, 180, 120, 0.92)], [T(20), c(150, 190, 80, 0.92)], [T(25), c(220, 200, 80, 0.92)], [T(30), c(228, 150, 60, 0.92)], [T(35), c(205, 80, 60, 0.92)], [T(42), c(160, 40, 70, 0.92)], [T(50), c(110, 20, 60, 0.92)]],
    ticks: [T(-10), T(0), T(5), T(10), T(15), T(20), T(25), T(30), T(35), T(40)],
    fmt: (v, u, d) => `${(d ? tempDelta(v, u.temp) : tempOf(v, u.temp)).toFixed(1)} ${tempLabel(u.temp)}`, unit: (u) => tempLabel(u.temp), disp: (v, u) => tempOf(v, u.temp),
  },
  rain: {
    id: 'rain', label: 'Rain', lo: 0, hi: 100, warp: 'sqrt', deltaFloor: 1,
    stops: [[0, c(120, 190, 255, 0)], [0.3, c(120, 190, 255, 0)], [0.8, c(110, 185, 255, 0.5)], [2, c(70, 150, 255, 0.72)], [5, c(45, 105, 245, 0.84)], [10, c(95, 75, 230, 0.9)], [20, c(170, 70, 215, 0.92)], [35, c(235, 80, 160, 0.93)], [60, c(255, 140, 70, 0.95)], [100, c(255, 225, 80, 0.96)]],
    ticks: [1, 2, 5, 10, 20, 35, 60, 100],
    fmt: (v) => `${v.toFixed(1)} mm/day`, unit: () => 'mm/day', disp: (v) => v,
  },
  pressure: {
    id: 'pressure', label: 'Pressure', lo: 98000, hi: 103500, warp: 'lin', deltaFloor: 100,
    stops: [[98000, c(80, 60, 150, 0.9)], [99300, c(60, 95, 175, 0.9)], [100200, c(70, 145, 185, 0.9)], [100800, c(90, 170, 150, 0.9)], [101300, c(150, 180, 100, 0.9)], [101900, c(210, 180, 80, 0.9)], [102600, c(210, 120, 70, 0.9)], [103500, c(170, 60, 70, 0.92)]],
    ticks: [99000, 99600, 100200, 100800, 101400, 102000, 102600],
    fmt: (v, u, d) => (d ? `${(pressOf(v, u.press)).toFixed(1)} ${pressLabel(u.press)}` : `${pressOf(v, u.press).toFixed(u.press === 'hPa' ? 1 : 0)} ${pressLabel(u.press)}`),
    unit: (u) => pressLabel(u.press), disp: (v, u) => pressOf(v, u.press),
  },
  moisture: {
    id: 'moisture', label: 'Moisture', lo: 0, hi: 75, warp: 'lin', deltaFloor: 1.5,
    stops: [[0, c(180, 160, 110, 0.85)], [10, c(170, 170, 120, 0.88)], [20, c(120, 170, 150, 0.9)], [30, c(80, 160, 170, 0.9)], [40, c(60, 130, 190, 0.92)], [50, c(70, 90, 180, 0.92)], [60, c(110, 70, 170, 0.93)], [75, c(160, 60, 150, 0.94)]],
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
  const key = `${layer.id}|${layer.label}|${layer.lo}|${layer.hi}`
  let l = lutCache.get(key)
  if (l) return l
  l = new Uint8ClampedArray(N * 4)
  for (let k = 0; k < N; k++) {
    const t = k / (N - 1)
    const x = layer.warp === 'sqrt' ? layer.lo + (layer.hi - layer.lo) * t * t : layer.lo + (layer.hi - layer.lo) * t
    const [r, g, b, a] = interpStops(layer.stops, x)
    l[k * 4] = r; l[k * 4 + 1] = g; l[k * 4 + 2] = b; l[k * 4 + 3] = a * 255
  }
  lutCache.set(key, l)
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
