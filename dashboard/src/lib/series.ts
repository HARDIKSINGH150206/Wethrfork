import type { LayerId } from './layers'
import { scalarAt } from './layers'
import { sample } from './interp'
import { CELLS } from './grid'

const buf = new Float32Array(CELLS)

/** Value of a layer at (lat, lon) on each of the 10 forecast days. */
export function pointSeries(roll: Float32Array, id: LayerId, lat: number, lon: number): number[] {
  const out: number[] = []
  for (let d = 0; d < 10; d++) out.push(sample(scalarAt(roll, d, id, buf), lat, lon))
  return out
}

/** Robust (98th percentile) magnitude of the difference between two rollouts over all days, for a stable delta scale. */
export function deltaScale(a: Float32Array, b: Float32Array, id: LayerId, floor: number): number {
  const x = new Float32Array(CELLS), y = new Float32Array(CELLS)
  const vals: number[] = []
  for (let d = 0; d < 10; d++) {
    scalarAt(a, d, id, x); scalarAt(b, d, id, y)
    for (let i = 0; i < CELLS; i++) vals.push(Math.abs(x[i] - y[i]))
  }
  vals.sort((p, q) => p - q)
  return Math.max(vals[Math.floor(vals.length * 0.985)] ?? 0, floor)
}
