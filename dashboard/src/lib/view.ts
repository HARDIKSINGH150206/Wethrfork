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
