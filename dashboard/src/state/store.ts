import { create } from 'zustand'
import { health, simulate } from '../api/judgeClient'
import { getMeta, getWindow, getWindows, postSensitivity, postVerdict } from '../api/labClient'
import type { Meta, Verdict, WindowInfo } from '../api/types'
import { CELLS, NC, flatten } from '../lib/grid'
import type { LayerId } from '../lib/layers'
import type { ShockSpec } from '../lib/shocks'
import type { Units } from '../lib/units'
import { DEFAULT_UNITS } from '../lib/units'

export interface Universe {
  id: string
  name: string
  perturbation: Float32Array | null
  box: [number, number, number, number] | null
  rollout: Float32Array | null
  verdict: Verdict | null
  status: 'loading' | 'ready' | 'error'
  error?: string
  wallMs?: number
}
export type Tab = 'map' | 'timeline' | 'validation' | 'about'
export type Drawer = 'shock' | 'audit' | null
export interface Pin { lat: number; lon: number }
export interface Focus { lat: number; lon: number; zoom: number; seq: number }
export interface Sens { map: Float32Array; lat: number; lon: number; lead: number; channel: string; top: string }

interface Store {
  meta: Meta | null
  windows: WindowInfo[]
  windowId: string | null
  init: Float32Array | null
  doy: [number, number] | null
  truth: Float32Array | null
  clim: Float32Array | null
  weekday: number | null
  universes: Record<string, Universe>
  order: string[]
  selected: string
  labOnline: boolean
  judgeOnline: boolean
  // map state
  tab: Tab
  tf: number // fractional day, 0-based (0 = day +1)
  playing: boolean
  speed: number
  layer: LayerId
  units: Units
  delta: boolean
  compare: boolean
  compareX: number
  showRings: boolean
  showIsobars: boolean
  showParticles: boolean
  showStipple: boolean
  pin: Pin | null
  drawMode: boolean
  drawnBox: [number, number, number, number] | null
  drawer: Drawer
  sens: Sens | null
  sensBusy: boolean
  menuOpen: boolean
  meteo: boolean
  focus: Focus | null
  boot: () => Promise<void>
  selectWindow: (id: string) => Promise<void>
  fork: (spec: ShockSpec) => Promise<void>
  select: (id: string) => void
  set: (p: Partial<Store>) => void
  setUnits: (u: Partial<Units>) => void
  runSensitivity: (lat: number, lon: number) => Promise<void>
}

export const CONTROL = 'control'
const TARGET_CHANNEL: Record<LayerId, string> = { wind: 'u10', temp: 't2m', rain: 'tp', pressure: 'msl', moisture: 'tcwv' }

export const useStore = create<Store>((set, get) => ({
  meta: null, windows: [], windowId: null, init: null, doy: null, truth: null, clim: null, weekday: null,
  universes: {}, order: [], selected: CONTROL, labOnline: false, judgeOnline: false,
  tab: 'map', tf: 0, playing: false, speed: 1, layer: 'wind', units: DEFAULT_UNITS, delta: false, compare: false, compareX: 0.5,
  showRings: true, showIsobars: false, showParticles: true, showStipple: false, pin: null, drawMode: false, drawnBox: null,
  drawer: null, sens: null, sensBusy: false, menuOpen: false, meteo: false, focus: null,

  set: (p) => set(p),
  setUnits: (u) => set((s) => ({ units: { ...s.units, ...u } })),

  boot: async () => {
    set({ judgeOnline: await health() })
    try {
      const [meta, windows] = await Promise.all([getMeta(), getWindows()])
      set({ meta, windows, labOnline: true })
      if (windows.length) await get().selectWindow(windows[0].id)
    } catch {
      set({ labOnline: false })
    }
  },

  selectWindow: async (id) => {
    const w = await getWindow(id)
    const init = flatten(w.init_states)
    const doy = w.doy_sincos
    const control: Universe = { id: CONTROL, name: 'Control', perturbation: null, box: null, rollout: null, verdict: null, status: 'loading' }
    set({
      windowId: id, init, doy, truth: w.truth ? flatten(w.truth) : null, clim: w.clim ? flatten(w.clim) : null, weekday: w.weekday ?? null,
      universes: { [CONTROL]: control }, order: [CONTROL], selected: CONTROL, tf: 0, pin: null, sens: null, drawnBox: null, meteo: false,
    })
    try {
      const r = await simulate(init, doy, null)
      set((s) => ({ universes: { ...s.universes, [CONTROL]: { ...control, rollout: r.rollout, status: 'ready', wallMs: r.wallMs } } }))
    } catch (e) {
      set((s) => ({ universes: { ...s.universes, [CONTROL]: { ...control, status: 'error', error: String(e) } } }))
    }
  },

  fork: async (spec) => {
    const { init, doy } = get()
    if (!init || !doy) return
    const id = `u${Date.now().toString(36)}`
    const uni: Universe = { id, name: spec.name, perturbation: spec.perturbation, box: spec.box, rollout: null, verdict: null, status: 'loading' }
    set((s) => ({ universes: { ...s.universes, [id]: uni }, order: [...s.order, id], selected: id, drawnBox: null, drawMode: false }))
    const verdictCall = get().labOnline
      ? postVerdict({ init_states: Array.from(init), doy_sincos: doy, perturbation: Array.from(spec.perturbation), box: spec.box, steps: 10 }).catch(() => null)
      : Promise.resolve(null)
    try {
      const [r, v] = await Promise.all([simulate(init, doy, spec.perturbation), verdictCall])
      set((s) => ({ universes: { ...s.universes, [id]: { ...uni, rollout: r.rollout, verdict: v, status: 'ready', wallMs: r.wallMs } } }))
    } catch (e) {
      set((s) => ({ universes: { ...s.universes, [id]: { ...uni, status: 'error', error: String(e) } } }))
    }
  },

  select: (id) => set({ selected: id }),

  runSensitivity: async (lat, lon) => {
    const { init, doy, layer, tf, meta } = get()
    if (!init || !doy || !meta) return
    const i = Math.round(lat - 6.5), j = Math.round(lon - 65.5)
    if (i < 0 || j < 0 || i > 31 || j > 35) return
    const channel = TARGET_CHANNEL[layer]
    const lead = Math.min(Math.max(Math.round(tf) + 1, 1), 10)
    set({ sensBusy: true })
    try {
      const r = await postSensitivity({ init_states: Array.from(init), doy_sincos: doy, target: { cells: [[i, j]], channel, lead } })
      const g = flatten(r.grad) // [6,32,36] gradient wrt the last input day
      const map = new Float32Array(CELLS)
      for (let c = 0; c < NC; c++) for (let k = 0; k < CELLS; k++) map[k] += Math.abs(g[c * CELLS + k]) * (meta.std[c] ?? 1)
      set({ sens: { map, lat, lon, lead, channel, top: r.top_channel }, sensBusy: false })
    } catch {
      set({ sensBusy: false })
    }
  },
}))
