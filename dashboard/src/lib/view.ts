import { LAT_MAX, LAT_MIN, LON_MAX, LON_MIN } from './interp'

/** Equirectangular view: `scale` pixels per degree, centred on (cx lon, cy lat). */
export interface View { scale: number; cx: number; cy: number; w: number; h: number }

/** Fit the whole model domain into the free area (room is left at the bottom for the timeline bar). */
export function fitView(w: number, h: number, top = 6, bottom = 104): View {
  const s = Math.min(w / (LON_MAX - LON_MIN), Math.max(h - top - bottom, 100) / (LAT_MAX - LAT_MIN))
  const latC = (LAT_MIN + LAT_MAX) / 2
  return { scale: s, cx: (LON_MIN + LON_MAX) / 2, cy: latC - (bottom - top) / 2 / s, w, h }
}
export const projX = (v: View, lon: number) => v.w / 2 + (lon - v.cx) * v.scale
export const projY = (v: View, lat: number) => v.h / 2 - (lat - v.cy) * v.scale
export const unprojLon = (v: View, x: number) => v.cx + (x - v.w / 2) / v.scale
export const unprojLat = (v: View, y: number) => v.cy - (y - v.h / 2) / v.scale

export function zoomAt(v: View, x: number, y: number, factor: number): View {
  const lon = unprojLon(v, x), lat = unprojLat(v, y)
  const base = fitView(v.w, v.h).scale
  const scale = Math.min(Math.max(v.scale * factor, base * 0.8), base * 14)
  return { ...v, scale, cx: lon - (x - v.w / 2) / scale, cy: lat + (y - v.h / 2) / scale }
}
export function panBy(v: View, dx: number, dy: number): View {
  return { ...v, cx: v.cx - dx / v.scale, cy: v.cy + dy / v.scale }
}

/** Fill the screen edge to edge (the model domain covers the viewport, as a weather map does). */
export function coverView(w: number, h: number, bottom = 44): View {
  const s = Math.max(w / (LON_MAX - LON_MIN), (h - bottom) / (LAT_MAX - LAT_MIN))
  return clampView({ scale: s, cx: 82.5, cy: 21.5, w, h }, bottom)
}

/** Keep the data under the whole screen when zoomed in at least to "cover"; otherwise centre the domain. */
export function clampView(v: View, bottom = 44): View {
  const halfW = v.w / 2 / v.scale, halfH = v.h / 2 / v.scale
  const usableTop = LAT_MAX, usableBottom = LAT_MIN - bottom / v.scale
  let cx = v.cx, cy = v.cy
  if (2 * halfW <= LON_MAX - LON_MIN) cx = Math.min(Math.max(cx, LON_MIN + halfW), LON_MAX - halfW)
  else cx = (LON_MIN + LON_MAX) / 2
  if (2 * halfH <= usableTop - usableBottom) cy = Math.min(Math.max(cy, usableBottom + halfH), usableTop - halfH)
  else cy = (LAT_MIN + LAT_MAX) / 2 - bottom / 2 / v.scale
  return { ...v, cx, cy }
}
