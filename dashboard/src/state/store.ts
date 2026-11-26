import { create } from 'zustand'
import { health, simulate } from '../api/judgeClient'
import { getMeta, getWindow, getWindows, postVerdict } from '../api/labClient'
import type { Channel, Meta, Verdict, WindowInfo } from '../api/types'
import { flatten } from '../lib/grid'
import type { ShockSpec } from '../lib/shocks'

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

interface Store {
  meta: Meta | null
  windows: WindowInfo[]
  windowId: string | null
  init: Float32Array | null
  doy: [number, number] | null
  truth: Float32Array | null
  universes: Record<string, Universe>
  order: string[]
  selected: string
  day: number // 0-based
  channel: Channel
  labOnline: boolean
  judgeOnline: boolean
  boot: () => Promise<void>
  selectWindow: (id: string) => Promise<void>
  fork: (spec: ShockSpec) => Promise<void>
  select: (id: string) => void
  setDay: (d: number) => void
  setChannel: (c: Channel) => void
}

export const CONTROL = 'control'

export const useStore = create<Store>((set, get) => ({
  meta: null,
  windows: [],
  windowId: null,
  init: null,
  doy: null,
  truth: null,
  universes: {},
  order: [],
  selected: CONTROL,
  day: 0,
  channel: 't2m',
  labOnline: false,
  judgeOnline: false,

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
    set({ windowId: id, init, doy, truth: w.truth ? flatten(w.truth) : null, universes: { [CONTROL]: control }, order: [CONTROL], selected: CONTROL, day: 0 })
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
    set((s) => ({ universes: { ...s.universes, [id]: uni }, order: [...s.order, id], selected: id }))
    const verdictCall = get().labOnline
      ? postVerdict({
          init_states: Array.from(init), doy_sincos: doy, perturbation: Array.from(spec.perturbation), box: spec.box, steps: 10,
        }).catch(() => null)
      : Promise.resolve(null)
    try {
      const [r, v] = await Promise.all([simulate(init, doy, spec.perturbation), verdictCall])
      set((s) => ({ universes: { ...s.universes, [id]: { ...uni, rollout: r.rollout, verdict: v, status: 'ready', wallMs: r.wallMs } } }))
    } catch (e) {
      set((s) => ({ universes: { ...s.universes, [id]: { ...uni, status: 'error', error: String(e) } } }))
    }
  },

  select: (id) => set({ selected: id }),
  setDay: (d) => set({ day: d }),
  setChannel: (c) => set({ channel: c }),
}))
