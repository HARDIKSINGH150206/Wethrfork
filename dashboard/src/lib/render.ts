import { contours } from 'd3-contour'
import type { LayerDef } from './layers'
import { divergingIndex, divergingLut, lut, lutIndex } from './layers'
import { NLAT, NLON } from './grid'
import { LAT0, LON0, sample } from './interp'

/** Raster resolution: pixels per degree of the pre-rendered field image (domain is 36 x 32 degrees). */
export const S = 8
export const RW = NLON * S
export const RH = NLAT * S

// per-pixel bilinear taps, computed once
const i0 = new Int16Array(RW * RH), j0 = new Int16Array(RW * RH), fy = new Float32Array(RW * RH), fx = new Float32Array(RW * RH)
;(() => {
  for (let py = 0; py < RH; py++) {
    const lat = 38 - (py + 0.5) / S
    const y = Math.min(Math.max(lat - LAT0, 0), NLAT - 1)
    for (let px = 0; px < RW; px++) {
      const lon = 65 + (px + 0.5) / S
      const x = Math.min(Math.max(lon - LON0, 0), NLON - 1)
      const k = py * RW + px
      i0[k] = Math.min(Math.floor(y), NLAT - 2); j0[k] = Math.min(Math.floor(x), NLON - 2)
      fy[k] = y - i0[k]; fx[k] = x - j0[k]
    }
  }
})()

export function makeRaster(): HTMLCanvasElement {
  const c = document.createElement('canvas')
  c.width = RW; c.height = RH
  return c
}

/** Paint a scalar field. With `dmax` it is drawn as a diverging delta, otherwise through the layer palette. */
export function paintField(canvas: HTMLCanvasElement, f: Float32Array, layer: LayerDef, dmax: number | null): void {
  const g = canvas.getContext('2d')!
  const img = g.createImageData(RW, RH)
  const px = img.data
  const table = dmax === null ? lut(layer) : divergingLut()
  for (let k = 0; k < RW * RH; k++) {
    const a = i0[k] * NLON + j0[k]
    const wx = fx[k], wy = fy[k]
    const v = (f[a] * (1 - wx) + f[a + 1] * wx) * (1 - wy) + (f[a + NLON] * (1 - wx) + f[a + NLON + 1] * wx) * wy
    const t = (dmax === null ? lutIndex(layer, v) : divergingIndex(v, dmax))
    const o = k * 4
    px[o] = table[t]; px[o + 1] = table[t + 1]; px[o + 2] = table[t + 2]; px[o + 3] = table[t + 3]
  }
  g.putImageData(img, 0, 0)
}

/** Dark base map: ocean gradient, land from the land-sea mask, subtle relief from orography. */
export function paintBase(canvas: HTMLCanvasElement, mask: number[][], oro: number[][]): void {
  const g = canvas.getContext('2d')!
  const img = g.createImageData(RW, RH)
  const m = Float32Array.from(mask.flat()), o = Float32Array.from(oro.flat())
  for (let py = 0; py < RH; py++) {
    const lat = 38 - (py + 0.5) / S
    for (let px = 0; px < RW; px++) {
      const lon = 65 + (px + 0.5) / S
      const land = sample(m, lat, lon)
      const e = sample(o, lat, lon) / 1000
      const k = (py * RW + px) * 4
      const t = Math.min(Math.max((land - 0.35) / 0.3, 0), 1) // soft coast
      const sea = [14 + (lat - 6) * 0.35, 30 + (lat - 6) * 0.5, 48 + (lat - 6) * 0.6]
      const shade = Math.min(e * 14, 38)
      const ld = [38 + shade, 52 + shade, 44 + shade * 0.9]
      img.data[k] = sea[0] + (ld[0] - sea[0]) * t
      img.data[k + 1] = sea[1] + (ld[1] - sea[1]) * t
      img.data[k + 2] = sea[2] + (ld[2] - sea[2]) * t
      img.data[k + 3] = 255
    }
  }
  g.putImageData(img, 0, 0)
}

export type Polyline = [number, number][] // [lon, lat]
export interface Contour { level: number; lines: Polyline[] }

/** Contour lines of a [32*36] field on a 4x upsampled grid. Coordinates returned as lon/lat. */
export function contourLines(f: Float32Array, levels: number[], U = 4): Contour[] {
  const w = NLON * U, h = NLAT * U
  const grid = new Float64Array(w * h)
  for (let y = 0; y < h; y++) {
    const lat = 6 + (y + 0.5) / U
    for (let x = 0; x < w; x++) grid[y * w + x] = sample(f, lat, 65 + (x + 0.5) / U)
  }
  // d3 indexes rows downward; flip so that row 0 is the north edge like the canvas
  const flipped = new Float64Array(w * h)
  for (let y = 0; y < h; y++) flipped.set(grid.subarray((h - 1 - y) * w, (h - y) * w), y * w)
  const gen = contours().size([w, h]).thresholds(levels)
  return gen(Array.from(flipped)).map((mp) => ({
    level: mp.value,
    lines: mp.coordinates.flatMap((poly) => poly.map((ring) => ring.map(([x, y]) => [65 + x / U, 38 - y / U] as [number, number]))),
  }))
}

export function coastline(mask: number[][]): Polyline[] {
  return contourLines(Float32Array.from(mask.flat()), [0.5], 4)[0]?.lines ?? []
}

/** Hillshade from orography (light from the north-west), neutral grey over flat ground; blended with soft-light. */
export function paintRelief(canvas: HTMLCanvasElement, oro: number[][]): void {
  const g = canvas.getContext('2d')!
  const img = g.createImageData(RW, RH)
  const o = Float32Array.from(oro.flat())
  const d = 0.35
  for (let py = 0; py < RH; py++) {
    const lat = 38 - (py + 0.5) / S
    for (let px = 0; px < RW; px++) {
      const lon = 65 + (px + 0.5) / S
      const dzdx = (sample(o, lat, lon + d) - sample(o, lat, lon - d)) / (2 * d * 1000) // km per degree
      const dzdy = (sample(o, lat + d, lon) - sample(o, lat - d, lon)) / (2 * d * 1000)
      const shade = Math.min(Math.max(0.5 + 0.16 * (dzdx * 0.707 - dzdy * 0.707) * 2.2, 0.08), 0.92)
      const k = (py * RW + px) * 4
      img.data[k] = img.data[k + 1] = img.data[k + 2] = shade * 255
      img.data[k + 3] = 255
    }
  }
  g.putImageData(img, 0, 0)
}
