import { CITIES } from './cities'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const CUM = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335, 366]

/** Recover the climatology slot (0..365, Feb 29 = 59) of the last input day from [sin, cos]. */
export function slotOf(doy: [number, number] | null): number {
  if (!doy) return 0
  const d = Math.round((Math.atan2(doy[0], doy[1]) * 365) / (2 * Math.PI))
  return ((d % 365) + 365) % 365
}

/** "Jul 18" for forecast day k (1-based) after the last input day. No year: the UI never shows one. */
export function dayLabel(doy: [number, number] | null, k: number): string {
  const s = (slotOf(doy) + k) % 366
  let m = 0
  while (s >= CUM[m + 1]) m++
  return `${MONTHS[m]} ${s - CUM[m] + 1}`
}

export function placeName(lat: number, lon: number): string {
  let best = '', bd = 1.2
  for (const c of CITIES) {
    const d = Math.hypot(c.lat - lat, (c.lon - lon) * Math.cos((lat * Math.PI) / 180))
    if (d < bd) { bd = d; best = c.name }
  }
  return best || `${lat.toFixed(2)}°N ${lon.toFixed(2)}°E`
}
