import { NLAT, NLON, latOf, lonOf } from './grid'

/** True where the cell lies within Euclidean distance `radius` (in cells) of the box. */
export function withinRadius(box: [number, number, number, number], radius: number): Uint8Array {
  const out = new Uint8Array(NLAT * NLON)
  const cells: [number, number][] = []
  for (let i = 0; i < NLAT; i++)
    for (let j = 0; j < NLON; j++) if (latOf(i) >= box[0] && latOf(i) <= box[1] && lonOf(j) >= box[2] && lonOf(j) <= box[3]) cells.push([i, j])
  if (!cells.length) return out
  for (let i = 0; i < NLAT; i++)
    for (let j = 0; j < NLON; j++) {
      let m = Infinity
      for (const [bi, bj] of cells) m = Math.min(m, Math.hypot(i - bi, j - bj))
      if (m <= radius) out[i * NLON + j] = 1
    }
  return out
}

/** The judge's no-teleport radius after `day` days (1-based): 3 + 8*day cells. */
export const judgeRadius = (day: number) => 3 + 8 * day
/** Our hard reach after `day` days. */
export const hardReach = (day: number) => 8 * day
