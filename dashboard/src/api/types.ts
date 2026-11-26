export type Channel = 't2m' | 'tp' | 'u10' | 'v10' | 'msl' | 'tcwv'
export const CHANNELS: Channel[] = ['t2m', 'tp', 'u10', 'v10', 'msl', 'tcwv']
export const UNITS: Record<Channel, string> = { t2m: 'K', tp: 'mm/day', u10: 'm/s', v10: 'm/s', msl: 'Pa', tcwv: 'kg/m²' }

/** Flat arrays: state [3*6*32*36], perturbation [6*32*36], rollout [steps*6*32*36]. */
export interface Meta {
  lat: number[]
  lon: number[]
  channels: Channel[]
  std: number[]
  mean: number[]
  land_sea_mask: number[][]
  speed_limit_cells_per_day: number
  model_name: string
  orography_m: number[][]
  sigma_err?: number[][][][] | null
}
export interface WindowInfo { id: string; label: string; season: string; doy: number }
export interface WindowData { id: string; init_states: number[][][][]; doy_sincos: [number, number]; truth?: number[][][][]; clim?: number[][][][] }
export interface Verdict {
  checks: { finite: boolean; nonzero: boolean; localized: boolean; propagates: boolean; stable: boolean }
  near_frac_day1: number
  far_frac_max: number
  max_z: number
  growth_ratio: number
  ood: { max_abs_z_vs_clim_std: number; level: 'inside' | 'edge' | 'extrapolating' }
  elapsed_ms: number
}
