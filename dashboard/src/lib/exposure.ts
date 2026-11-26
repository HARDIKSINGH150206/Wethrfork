import { CELLS, NLAT, NLON, latOf, lonOf } from './grid'

export interface Exposure {
  /** mean accumulated rainfall over the window, land cells, mm */
  ctlMm: number
  scnMm: number
  /** share of land AREA whose accumulated rainfall exceeds the declared threshold, 0..1 */
  ctlFrac: number
  scnFrac: number
  landCells: number
}

/** Days actually used: `n` consecutive days starting at `start`, shifted back if the window would run past day 10. */
export const windowStart = (start: number, n: number, steps = 10) => Math.max(0, Math.min(Math.round(start), steps - n))

function accumulate(roll: Float32Array, start: number, n: number, out: Float32Array): Float32Array {
  out.fill(0)
  for (let d = start; d < start + n; d++) {
    const off = (d * 6 + 1) * CELLS // channel 1 is daily rainfall in mm/day
    for (let i = 0; i < CELLS; i++) out[i] += Math.max(roll[off + i], 0)
  }
  return out
}

const A = new Float32Array(CELLS), B = new Float32Array(CELLS)

/**
 * Rainfall exposure of a region (or the whole domain when `box` is null): accumulated rainfall over `n` days and the share
 * of land area above `thresholdMm`, for the control and for the changed scenario. Cells are weighted by cos(latitude);
 * land is land_sea_mask >= 0.5. Pure arithmetic on the model's daily rainfall: no probabilities are implied.
 */
export function rainfallExposure(
  ctl: Float32Array, scn: Float32Array, start: number, n: number, thresholdMm: number, land: number[][],
  box: [number, number, number, number] | null,
): Exposure {
  const s0 = windowStart(start, n)
  accumulate(ctl, s0, n, A); accumulate(scn, s0, n, B)
  let w = 0, ca = 0, cb = 0, fa = 0, fb = 0, cells = 0
  for (let i = 0; i < NLAT; i++) {
    const lat = latOf(i), wt = Math.cos((lat * Math.PI) / 180)
    for (let j = 0; j < NLON; j++) {
      if (land[i][j] < 0.5) continue
      if (box) {
        const lon = lonOf(j)
        if (lat < box[0] || lat > box[1] || lon < box[2] || lon > box[3]) continue
      }
      const k = i * NLON + j
      w += wt; cells++
      ca += wt * A[k]; cb += wt * B[k]
      if (A[k] > thresholdMm) fa += wt
      if (B[k] > thresholdMm) fb += wt
    }
  }
  if (!w) return { ctlMm: NaN, scnMm: NaN, ctlFrac: NaN, scnFrac: NaN, landCells: 0 }
  return { ctlMm: ca / w, scnMm: cb / w, ctlFrac: fa / w, scnFrac: fb / w, landCells: cells }
}
