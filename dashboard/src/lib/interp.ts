import { CELLS, NLAT, NLON } from './grid'

export const LAT0 = 6.5
export const LON0 = 65.5
/** Domain edges in degrees (cell centres plus half a cell). */
export const LON_MIN = 65
export const LON_MAX = 101
export const LAT_MIN = 6
export const LAT_MAX = 38

/** Bilinear sample of a [32*36] field at (lat, lon) in degrees, clamped to the grid. */
export function sample(f: Float32Array, lat: number, lon: number): number {
  const y = Math.min(Math.max(lat - LAT0, 0), NLAT - 1)
  const x = Math.min(Math.max(lon - LON0, 0), NLON - 1)
  const i0 = Math.floor(y), j0 = Math.floor(x)
  const i1 = Math.min(i0 + 1, NLAT - 1), j1 = Math.min(j0 + 1, NLON - 1)
  const fy = y - i0, fx = x - j0
  const a = f[i0 * NLON + j0], b = f[i0 * NLON + j1], c = f[i1 * NLON + j0], d = f[i1 * NLON + j1]
  return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy
}

/** Linear blend of two equally sized fields into `out`. */
export function lerpInto(out: Float32Array, a: Float32Array, b: Float32Array, t: number): Float32Array {
  const n = Math.min(out.length, a.length)
  for (let i = 0; i < n; i++) out[i] = a[i] + (b[i] - a[i]) * t
  return out
}

/** Slice day `d`, channel `c` out of a rollout laid out [steps, 6, 32, 36]. */
export function dayField(roll: Float32Array, d: number, c: number): Float32Array {
  const off = (d * 6 + c) * CELLS
  return roll.subarray(off, off + CELLS)
}
