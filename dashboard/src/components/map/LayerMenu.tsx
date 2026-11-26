import type { ReactNode } from 'react'
import { IconDelta, IconDraw, IconMoist, IconParticles, IconPressure, IconRain, IconRing, IconSplit, IconTemp, IconWind } from '../icons'
import type { LayerId } from '../../lib/layers'
import { LAYER_ORDER, LAYERS } from '../../lib/layers'
import { CONTROL, useStore } from '../../state/store'

const ICON: Record<LayerId, ReactNode> = { wind: <IconWind />, temp: <IconTemp />, rain: <IconRain />, pressure: <IconPressure />, moisture: <IconMoist /> }
const LABEL: Record<LayerId, string> = { wind: 'Wind', temp: 'Temperature', rain: 'Rain', pressure: 'Pressure', moisture: 'Moisture' }

/** Right-hand overlay list: label on the left, round icon on the right, active item highlighted. */
export function LayerMenu() {
  const s = useStore()
  const forked = s.selected !== CONTROL
  const item = (key: string, label: string, icon: ReactNode, on: boolean, onClick: () => void, disabled = false, title = '') => (
    <button key={key} className={`ov ${on ? 'on' : ''}`} onClick={onClick} disabled={disabled} title={title}>
      <span className="lbl">{label}</span><span className="ic">{icon}</span>
    </button>
  )
  return (
    <aside className="overlays" data-ui>
      {LAYER_ORDER.map((id) => item(id, LABEL[id] ?? LAYERS[id].label, ICON[id], s.layer === id, () => s.set({ layer: id, sens: null })))}
      <div className="sep">Isolines &amp; tools</div>
      {item('iso', 'Pressure lines', <IconPressure />, s.showIsobars, () => s.set({ showIsobars: !s.showIsobars }))}
      {item('part', 'Particles', <IconParticles />, s.showParticles, () => s.set({ showParticles: !s.showParticles }))}
      {item('delta', 'Difference', <IconDelta />, s.delta, () => s.set({ delta: !s.delta, compare: false }), !forked, 'Universe minus control')}
      {item('cmp', 'Swipe compare', <IconSplit />, s.compare, () => s.set({ compare: !s.compare, delta: false }), !forked, 'Control on the left, universe on the right')}
      {item('ring', 'Speed limit', <IconRing />, s.showRings, () => s.set({ showRings: !s.showRings }))}
      {item('stip', 'Beyond error', <IconDelta />, s.showStipple, () => s.set({ showStipple: !s.showStipple }), !forked || !s.delta, 'Dots where the change exceeds measured forecast error')}
      {item('draw', 'Draw a shock', <IconDraw />, s.drawMode, () => s.set({ drawMode: !s.drawMode, drawer: 'shock' }))}
    </aside>
  )
}
