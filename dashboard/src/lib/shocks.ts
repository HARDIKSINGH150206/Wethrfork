import { CELLS, NC, NLAT, NLON, boxCells, latOf, lonOf } from './grid'

export interface ShockSpec {
  name: string
  perturbation: Float32Array // [6*32*36], physical units, added to the last input day
  box: [number, number, number, number] // lat_min, lat_max, lon_min, lon_max
}

const empty = () => new Float32Array(NC * CELLS)
const at = (c: number, i: number, j: number) => (c * NLAT + i) * NLON + j

/** The kit's warm_ocean: +3 K and +15% of the current tcwv over lat 8..20, lon 82..94. */
export function warmOcean(last: Float32Array): ShockSpec {
  const p = empty()
  for (const [i, j] of boxCells(8, 20, 82, 94)) {
    p[at(0, i, j)] = 3.0
    p[at(5, i, j)] = 0.15 * last[at(5, i, j)]
  }
  return { name: 'Warm Bay +3 K', perturbation: p, box: [8, 20, 82, 94] }
}

/** The kit's monsoon_stall: -40% of u10 and v10 over lat 8..20, lon 65..75. */
export function monsoonStall(last: Float32Array): ShockSpec {
  const p = empty()
  for (const [i, j] of boxCells(8, 20, 65, 75)) {
    p[at(2, i, j)] = -0.4 * last[at(2, i, j)]
    p[at(3, i, j)] = -0.4 * last[at(3, i, j)]
  }
  return { name: 'Monsoon stall -40% wind', perturbation: p, box: [8, 20, 65, 75] }
}

/** Gaussian bump on one channel. amplitude in physical units; coupled moisture follows Clausius-Clapeyron for t2m. */
export function gaussian(
  channel: number, amplitude: number, lat: number, lon: number, radius: number, couple = false, name = 'Gaussian shock',
): ShockSpec {
  const p = empty()
  let lo = [999, -999, 999, -999]
  for (let i = 0; i < NLAT; i++)
    for (let j = 0; j < NLON; j++) {
      const r2 = (latOf(i) - lat) ** 2 + (lonOf(j) - lon) ** 2
      const w = Math.exp(-r2 / (2 * radius * radius))
      if (w < 0.02) continue
      p[at(channel, i, j)] = amplitude * w
      if (couple && channel === 0) p[at(5, i, j)] = 0 // filled by caller with current tcwv if desired
      lo = [Math.min(lo[0], latOf(i)), Math.max(lo[1], latOf(i)), Math.min(lo[2], lonOf(j)), Math.max(lo[3], lonOf(j))]
    }
  return { name, perturbation: p, box: [lo[0], lo[1], lo[2], lo[3]] }
}

/** Cyclone-like vortex: msl low plus gradient-wind-balance winds rotated 15 degrees inward. */
export function cyclone(lat: number, lon: number, depthPa = 2000, radius = 2): ShockSpec {
  const p = empty()
  const omega = 7.292e-5
  const rho = 1.2
  let box: [number, number, number, number] = [999, -999, 999, -999]
  const cellM = 111200
  for (let i = 0; i < NLAT; i++)
    for (let j = 0; j < NLON; j++) {
      const dy = (latOf(i) - lat) * cellM
      const dx = (lonOf(j) - lon) * cellM * Math.cos((latOf(i) * Math.PI) / 180)
      const r = Math.hypot(dx, dy)
      const g = Math.exp(-(r * r) / (2 * (radius * cellM) ** 2))
      if (g < 0.02) continue
      p[at(4, i, j)] = -depthPa * g
      const f = 2 * omega * Math.sin((latOf(i) * Math.PI) / 180)
      const dpdr = (depthPa * g * r) / (radius * cellM) ** 2 // |dp/dr|
      const vg = Math.min(40, (-f * r) / 2 + Math.sqrt((f * r) ** 2 / 4 + (r * dpdr) / rho))
      const ang = Math.atan2(dy, dx) + Math.PI / 2 + (15 * Math.PI) / 180 // counter-clockwise plus inflow
      p[at(2, i, j)] = vg * Math.cos(ang) * g
      p[at(3, i, j)] = vg * Math.sin(ang) * g
      p[at(5, i, j)] = 6 * g
      box = [Math.min(box[0], latOf(i)), Math.max(box[1], latOf(i)), Math.min(box[2], lonOf(j)), Math.max(box[3], lonOf(j))]
    }
  return { name: 'Cyclone', perturbation: p, box }
}

export const heatDome = () => {
  const s = gaussian(0, 5, 27, 72, 4, false, 'Heat dome Rajasthan')
  for (let i = 0; i < NLAT; i++)
    for (let j = 0; j < NLON; j++) {
      const w = Math.exp(-((latOf(i) - 27) ** 2 + (lonOf(j) - 72) ** 2) / 32)
      s.perturbation[at(4, i, j)] = -300 * w
    }
  return s
}

export const dryKerala = (last: Float32Array) => {
  const s = gaussian(5, 0, 10, 76.5, 2, false, 'Dry Kerala')
  for (let i = 0; i < NLAT; i++)
    for (let j = 0; j < NLON; j++) {
      const w = Math.exp(-((latOf(i) - 10) ** 2 + (lonOf(j) - 76.5) ** 2) / 8)
      s.perturbation[at(5, i, j)] = -0.3 * last[at(5, i, j)] * w
    }
  return s
}

/** Rectangle shock on one channel. `relative` is a fraction of the current value (physical units otherwise). */
export function boxShock(channel: number, amount: number, relative: boolean, box: [number, number, number, number], last: Float32Array, name: string): ShockSpec {
  const p = empty()
  for (const [i, j] of boxCells(box[0], box[1], box[2], box[3])) p[at(channel, i, j)] = relative ? amount * last[at(channel, i, j)] : amount
  return { name, perturbation: p, box }
}
