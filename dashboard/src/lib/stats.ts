import { CELLS, NLAT, NLON } from './grid'
import type { LayerId } from './layers'
import { scalarAt } from './layers'

const LAT_W = (() => {
  const w = Array.from({ length: NLAT }, (_, i) => Math.cos(((6.5 + i) * Math.PI) / 180))
  const m = w.reduce((a, b) => a + b, 0) / NLAT
  return w.map((x) => x / m)
})()

export function rmseLat(a: Float32Array, b: Float32Array): number {
  let s = 0
  for (let i = 0; i < NLAT; i++) for (let j = 0; j < NLON; j++) { const d = a[i * NLON + j] - b[i * NLON + j]; s += LAT_W[i] * d * d }
  return Math.sqrt(s / CELLS)
}

/** Scalar of the last input day (state laid out [3,6,32,36]) for a layer. */
export function lastDayScalar(init: Float32Array, id: LayerId): Float32Array {
  const off = (2 * 6) * CELLS
  const out = new Float32Array(CELLS)
  if (id === 'wind') {
    for (let i = 0; i < CELLS; i++) out[i] = Math.hypot(init[off + 2 * CELLS + i], init[off + 3 * CELLS + i])
    return out
  }
  const ch = { temp: 0, rain: 1, pressure: 4, moisture: 5 }[id]
  out.set(init.subarray(off + ch * CELLS, off + (ch + 1) * CELLS))
  return out
}

export interface SkillRow { day: number; model: number; persist: number; clim: number | null; skill: number }

/** Per-day RMSE of the forecast, persistence and climatology against the truth, for one layer. */
export function skillByDay(model: Float32Array, truth: Float32Array, init: Float32Array, clim: Float32Array | null, id: LayerId): SkillRow[] {
  const p = lastDayScalar(init, id)
  const rows: SkillRow[] = []
  for (let d = 0; d < 10; d++) {
    const t = scalarAt(truth, d, id, new Float32Array(CELLS))
    const m = rmseLat(scalarAt(model, d, id, new Float32Array(CELLS)), t)
    const rp = rmseLat(p, t)
    const rc = clim ? rmseLat(scalarAt(clim, d, id, new Float32Array(CELLS)), t) : null
    const best = rc === null ? rp : Math.min(rp, rc)
    rows.push({ day: d + 1, model: m, persist: rp, clim: rc, skill: 1 - m / best })
  }
  return rows
}
