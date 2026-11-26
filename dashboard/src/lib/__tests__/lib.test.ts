import { describe, expect, it } from 'vitest'
import { CELLS, NLAT, NLON } from '../grid'
import { dayLabel, dayName, slotOf } from '../dates'
import { rainfallExposure, windowStart } from '../exposure'
import { sample } from '../interp'
import { LAYERS, lut, lutIndex, scalarAt } from '../layers'
import { pressOf, tempDelta, tempOf, windOf } from '../units'
import { clampView, coverView, fitView, projX, projY, unprojLat, unprojLon, zoomAt } from '../view'

/** A [10,6,32,36] rollout of zeros, with helpers to set daily rain. */
const roll = () => new Float32Array(10 * 6 * CELLS)
const setRain = (r: Float32Array, d: number, v: (i: number, j: number) => number) => {
  for (let i = 0; i < NLAT; i++) for (let j = 0; j < NLON; j++) r[(d * 6 + 1) * CELLS + i * NLON + j] = v(i, j)
}
const land = (f: (i: number, j: number) => number) => Array.from({ length: NLAT }, (_, i) => Array.from({ length: NLON }, (_, j) => f(i, j)))
const ALL_LAND = land(() => 1)

describe('units', () => {
  it('converts temperature', () => {
    expect(tempOf(273.15, 'C')).toBeCloseTo(0)
    expect(tempOf(373.15, 'C')).toBeCloseTo(100)
    expect(tempOf(273.15, 'F')).toBeCloseTo(32)
    expect(tempOf(300, 'K')).toBe(300)
  })
  it('converts temperature DIFFERENCES without the offset', () => {
    expect(tempDelta(5, 'C')).toBe(5)
    expect(tempDelta(5, 'F')).toBeCloseTo(9)
  })
  it('converts wind and pressure', () => {
    expect(windOf(10, 'kmh')).toBeCloseTo(36)
    expect(windOf(10, 'kt')).toBeCloseTo(19.44, 1)
    expect(pressOf(101325, 'hPa')).toBeCloseTo(1013.25)
    expect(pressOf(101325, 'mmHg')).toBeCloseTo(760, 0)
  })
})

describe('dates', () => {
  const sc = (slot: number): [number, number] => [Math.sin((2 * Math.PI * slot) / 365), Math.cos((2 * Math.PI * slot) / 365)]
  it('recovers every slot from sin/cos', () => { for (let s = 0; s < 365; s++) expect(slotOf(sc(s))).toBe(s) })
  it('labels days, wrapping the year and including Feb 29 (slot 59)', () => {
    expect(dayLabel(sc(0), 1)).toBe('Jan 2')
    expect(dayLabel(sc(58), 1)).toBe('Feb 29')
    expect(dayLabel(sc(58), 2)).toBe('Mar 1')
    expect(dayLabel(sc(364), 1)).toBe('Dec 31')
    expect(dayLabel(sc(364), 2)).toBe('Jan 1')
  })
  it('names weekdays with wrap-around and falls back without one', () => {
    expect(dayName(sc(0), 1, 3)).toBe('Friday 2') // last input day is a Thursday (3): +1 day is Friday
    expect(dayName(sc(0), 4, 3, true)).toBe('Mon 5')
    expect(dayName(sc(0), 1, null)).toBe('Jan 2')
    expect(dayName(null, 1, null)).toMatch(/^[A-Z][a-z]{2} \d+$/)
  })
})

describe('sampling and colour tables', () => {
  it('interpolates bilinearly and clamps outside the grid', () => {
    const f = new Float32Array(CELLS)
    for (let i = 0; i < NLAT; i++) for (let j = 0; j < NLON; j++) f[i * NLON + j] = i + 10 * j
    expect(sample(f, 6.5, 65.5)).toBe(0)
    expect(sample(f, 7.0, 66.0)).toBeCloseTo(0.5 + 5)
    expect(sample(f, -50, -50)).toBe(0)
    expect(sample(f, 99, 999)).toBe(31 + 350)
  })
  it('colour lookup is monotone in range and never out of bounds', () => {
    for (const d of Object.values(LAYERS)) {
      const t = lut(d)
      for (const v of [-1e9, d.lo, (d.lo + d.hi) / 2, d.hi, 1e9, NaN]) {
        const k = lutIndex(d, v)
        expect(Number.isInteger(k) || Number.isNaN(k)).toBe(true)
        if (!Number.isNaN(k)) expect(k).toBeLessThan(t.length)
      }
    }
  })
  it('scalarAt blends in time and computes wind speed', () => {
    const r = roll()
    for (let i = 0; i < CELLS; i++) { r[(0 * 6 + 2) * CELLS + i] = 3; r[(0 * 6 + 3) * CELLS + i] = 4; r[(1 * 6 + 2) * CELLS + i] = 6; r[(1 * 6 + 3) * CELLS + i] = 8 }
    expect(scalarAt(r, 0, 'wind')[0]).toBeCloseTo(5)
    expect(scalarAt(r, 1, 'wind')[0]).toBeCloseTo(10)
    expect(scalarAt(r, 0.5, 'wind')[0]).toBeCloseTo(7.5)
    expect(scalarAt(r, 9.9, 'wind')[0]).toBeDefined()
  })
})

describe('rainfall exposure', () => {
  it('accumulates exactly three days and counts land area above the threshold', () => {
    const a = roll(), b = roll()
    for (let d = 0; d < 10; d++) { setRain(a, d, () => 10); setRain(b, d, () => 10) }
    setRain(b, 4, () => 40) // scenario: one very wet day inside the window starting at day 3
    const e = rainfallExposure(a, b, 3, 3, 50, ALL_LAND, null)
    expect(e.ctlMm).toBeCloseTo(30)
    expect(e.scnMm).toBeCloseTo(60)
    expect(e.ctlFrac).toBe(0)
    expect(e.scnFrac).toBe(1)
    expect(e.landCells).toBe(CELLS)
  })
  it('threshold is strict (> not >=) and ocean cells are excluded', () => {
    const a = roll(), b = roll()
    for (let d = 0; d < 10; d++) { setRain(a, d, () => 10); setRain(b, d, () => 10) }
    const half = land((_, j) => (j < NLON / 2 ? 1 : 0))
    expect(rainfallExposure(a, b, 0, 3, 30, half, null).ctlFrac).toBe(0) // exactly 30 is not above 30
    expect(rainfallExposure(a, b, 0, 3, 29.99, half, null).ctlFrac).toBe(1) // all LAND exceeds; the ocean half does not dilute it
    expect(rainfallExposure(a, b, 0, 3, 29.99, half, null).landCells).toBe(CELLS / 2)
  })
  it('weights cells by cos(latitude) and respects a region box', () => {
    const a = roll(), b = roll()
    for (let d = 0; d < 10; d++) { setRain(a, d, (i) => (i === 0 ? 100 : 0)); setRain(b, d, (i) => (i === 0 ? 100 : 0)) }
    const e = rainfallExposure(a, b, 0, 3, 50, ALL_LAND, null)
    const wts = Array.from({ length: NLAT }, (_, i) => Math.cos(((6.5 + i) * Math.PI) / 180))
    expect(e.ctlFrac).toBeCloseTo(wts[0] / wts.reduce((x, y) => x + y, 0), 6) // southern row only, area-weighted
    const box = rainfallExposure(a, b, 0, 3, 50, ALL_LAND, [6, 8, 65, 101])
    expect(box.ctlFrac).toBeCloseTo(wts[0] / (wts[0] + wts[1]), 6)
    expect(rainfallExposure(a, b, 0, 3, 50, ALL_LAND, [100, 101, 0, 1]).landCells).toBe(0) // empty region
  })
  it('never lets negative rain reduce the accumulation, and shifts a window that runs past day 10', () => {
    const a = roll()
    setRain(a, 0, () => -50)
    expect(rainfallExposure(a, a, 0, 3, 1, ALL_LAND, null).ctlMm).toBe(0)
    expect(windowStart(9, 3)).toBe(7)
    expect(windowStart(-4, 3)).toBe(0)
    expect(windowStart(4.6, 3)).toBe(5)
  })
})

describe('map view', () => {
  it('projection round-trips', () => {
    const v = fitView(1600, 900)
    expect(unprojLon(v, projX(v, 80))).toBeCloseTo(80)
    expect(unprojLat(v, projY(v, 20))).toBeCloseTo(20)
  })
  it('cover view fills the screen and clamping never leaves the model domain empty', () => {
    const v = coverView(1600, 900)
    for (const [dx, dy] of [[1e6, 0], [-1e6, 0], [0, 1e6], [0, -1e6]]) {
      const c = clampView({ ...v, cx: v.cx + dx, cy: v.cy + dy })
      expect(Math.abs(c.cx - v.cx)).toBeLessThan(40)
      expect(Number.isFinite(c.cx) && Number.isFinite(c.cy)).toBe(true)
    }
  })
  it('zoom keeps the point under the cursor fixed and limits the zoom range', () => {
    const v = fitView(1600, 900)
    const z = zoomAt(v, 400, 300, 2)
    expect(unprojLon(z, 400)).toBeCloseTo(unprojLon(v, 400), 6)
    expect(unprojLat(z, 300)).toBeCloseTo(unprojLat(v, 300), 6)
    expect(zoomAt(v, 0, 0, 1e9).scale).toBeLessThan(v.scale * 20)
    expect(zoomAt(v, 0, 0, 1e-9).scale).toBeGreaterThan(0)
  })
})
