export type TempUnit = 'C' | 'F' | 'K'
export type WindUnit = 'ms' | 'kmh' | 'kt'
export type PressUnit = 'hPa' | 'mmHg'
export interface Units { temp: TempUnit; wind: WindUnit; press: PressUnit }
export const DEFAULT_UNITS: Units = { temp: 'C', wind: 'ms', press: 'hPa' }

export const tempOf = (k: number, u: TempUnit) => (u === 'C' ? k - 273.15 : u === 'F' ? ((k - 273.15) * 9) / 5 + 32 : k)
export const tempDelta = (k: number, u: TempUnit) => (u === 'F' ? (k * 9) / 5 : k)
export const windOf = (ms: number, u: WindUnit) => (u === 'ms' ? ms : u === 'kmh' ? ms * 3.6 : ms * 1.943844)
export const pressOf = (pa: number, u: PressUnit) => (u === 'hPa' ? pa / 100 : pa * 0.00750062)

export const tempLabel = (u: TempUnit) => (u === 'K' ? 'K' : `°${u}`)
export const windLabel = (u: WindUnit) => ({ ms: 'm/s', kmh: 'km/h', kt: 'kt' })[u]
export const pressLabel = (u: PressUnit) => u

export const NEXT_TEMP: Record<TempUnit, TempUnit> = { C: 'F', F: 'K', K: 'C' }
export const NEXT_WIND: Record<WindUnit, WindUnit> = { ms: 'kmh', kmh: 'kt', kt: 'ms' }
export const NEXT_PRESS: Record<PressUnit, PressUnit> = { hPa: 'mmHg', mmHg: 'hPa' }
