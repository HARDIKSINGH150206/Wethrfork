import { create } from 'zustand'
import type { View } from '../lib/view'
import { clampView, fitView, zoomAt } from '../lib/view'

/**
 * Map camera and cursor, kept apart from the main store so that moving the mouse re-renders only the small readouts
 * (coordinates, scale bar) and never the map itself.
 */
interface MapCtl {
  view: View
  hover: { lat: number; lon: number } | null
  setView: (v: View | ((v: View) => View)) => void
  setHover: (h: { lat: number; lon: number } | null) => void
  zoomBy: (factor: number) => void
  fit: () => void
}

export const useMap = create<MapCtl>((set, get) => ({
  view: fitView(800, 600),
  hover: null,
  setView: (v) => set((s) => ({ view: typeof v === 'function' ? v(s.view) : v })),
  setHover: (hover) => set({ hover }),
  zoomBy: (f) => { const v = get().view; set({ view: clampView(zoomAt(v, v.w / 2, v.h / 2, f)) }) },
  fit: () => { const v = get().view; set({ view: fitView(v.w, v.h, 70, 90) }) },
}))
