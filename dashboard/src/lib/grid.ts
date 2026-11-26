import type { Channel } from '../api/types'
import { CHANNELS } from '../api/types'

export const NLAT = 32
export const NLON = 36
export const NC = 6
export const CELLS = NLAT * NLON
export const LAT0 = 6.5
export const LON0 = 65.5

export const chIndex = (c: Channel) => CHANNELS.indexOf(c)
export const latOf = (i: number) => LAT0 + i
export const lonOf = (j: number) => LON0 + j

/** Flatten nested JSON [..., 32, 36] to a Float32Array. */
export function flatten(a: unknown): Float32Array {
  const out: number[] = []
  const walk = (x: unknown) => {
    if (Array.isArray(x)) x.forEach(walk)
    else out.push(x as number)
  }
  walk(a)
  return Float32Array.from(out)
}

/** Slice day `d` (0-based), channel `c` out of a rollout laid out [steps, 6, 32, 36]. */
export function field(roll: Float32Array, d: number, c: number): Float32Array {
  const off = (d * NC + c) * CELLS
  return roll.subarray(off, off + CELLS)
}

export function diff(a: Float32Array, b: Float32Array): Float32Array {
  const o = new Float32Array(a.length)
  for (let i = 0; i < a.length; i++) o[i] = a[i] - b[i]
  return o
}

/** Cell (i,j) with lat0..lat1 / lon0..lon1 inclusive on cell centres, same rule as the judge. */
export function boxCells(lat0: number, lat1: number, lon0: number, lon1: number): [number, number][] {
  const out: [number, number][] = []
  for (let i = 0; i < NLAT; i++)
    for (let j = 0; j < NLON; j++) {
      const la = latOf(i), lo = lonOf(j)
      if (la >= lat0 && la <= lat1 && lo >= lon0 && lo <= lon1) out.push([i, j])
    }
  return out
}
