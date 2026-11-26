import type { ReactNode } from 'react'
import { IconDelta, IconDraw, IconMoist, IconParticles, IconPressure, IconRain, IconRing, IconSplit, IconTemp, IconWind } from '../icons'
import type { LayerId } from '../../lib/layers'
import { LAYER_ORDER, LAYERS } from '../../lib/layers'
import { CONTROL, useStore } from '../../state/store'

const ICON: Record<LayerId, ReactNode> = { wind: <IconWind />, temp: <IconTemp />, rain: <IconRain />, pressure: <IconPressure />, moisture: <IconMoist /> }

export function LayerMenu() {
  const s = useStore()
  const forked = s.selected !== CONTROL
  const toggle = (k: 'showParticles' | 'showIsobars' | 'showRings', icon: ReactNode, label: string) => (
    <button className={`chip ${s[k] ? 'on' : ''}`} onClick={() => s.set({ [k]: !s[k] })} title={label}>{icon}<span>{label}</span></button>
  )
  return (
    <aside className="layers" data-ui>
      {LAYER_ORDER.map((id) => (
        <button key={id} className={`layer ${s.layer === id ? 'on' : ''}`} onClick={() => s.set({ layer: id, sens: null })}>
          {ICON[id]}<span>{LAYERS[id].label}</span>
        </button>
      ))}
      <hr />
      <button className={`chip ${s.delta ? 'on' : ''}`} disabled={!forked} onClick={() => s.set({ delta: !s.delta, compare: false })} title="Show the difference from the control"><IconDelta /><span>Delta</span></button>
      <button className={`chip ${s.compare ? 'on' : ''}`} disabled={!forked} onClick={() => s.set({ compare: !s.compare, delta: false })} title="Swipe between control and universe"><IconSplit /><span>Compare</span></button>
      {toggle('showParticles', <IconParticles />, 'Particles')}
      {toggle('showIsobars', <IconPressure />, 'Isobars')}
      {toggle('showRings', <IconRing />, 'Speed limit')}
      <button className={`chip ${s.showStipple ? 'on' : ''}`} disabled={!forked || !s.delta} onClick={() => s.set({ showStipple: !s.showStipple })} title="Dots where the response exceeds measured forecast error"><IconDelta /><span>Beyond error</span></button>
      <button className={`chip ${s.drawMode ? 'on' : ''}`} onClick={() => s.set({ drawMode: !s.drawMode, drawer: 'shock' })} title="Drag a rectangle on the map to place a shock"><IconDraw /><span>Draw shock</span></button>
    </aside>
  )
}
