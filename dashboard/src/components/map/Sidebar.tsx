import { useState } from 'react'
import type { ReactNode } from 'react'
import { IconCheck, IconChevron, IconFork, IconMoist, IconPressure, IconRain, IconShield, IconTemp, IconWind, Mark } from '../icons'
import type { LayerId } from '../../lib/layers'
import { CONTROL, useStore } from '../../state/store'

const MAPS: [LayerId, string, ReactNode][] = [
  ['rain', 'Precipitation', <IconRain key="r" />],
  ['wind', 'Wind', <IconWind key="w" />],
  ['temp', 'Temperature', <IconTemp key="t" />],
  ['moisture', 'Moisture', <IconMoist key="m" />],
  ['pressure', 'Pressure', <IconPressure key="p" />],
]

/** Top-left: the logo tile and the map menu (forecast maps, then forks), styled like a satellite-map menu. */
export function Sidebar() {
  const s = useStore()
  const [open, setOpen] = useState(true)
  const forked = s.selected !== CONTROL
  const check = (label: string, on: boolean, onClick: () => void, disabled = false, title = '') => (
    <button className={`sub ${on ? 'on' : ''}`} onClick={onClick} disabled={disabled} title={title}>
      <i>{on && <IconCheck />}</i>{label}
    </button>
  )
  return (
    <>
      <button className="logo panel" data-ui onClick={() => s.set({ panel: s.panel === 'info' ? null : 'info' })} aria-label="About Wethrfork">
        <Mark /><span className="word"><b>WETHR</b><span>FORK</span></span>
      </button>
      <nav className="maps panel" data-ui aria-label="Maps">
        <button className="head" onClick={() => setOpen(!open)} aria-expanded={open}>
          <h5>Forecast maps</h5><IconChevron up={open} />
        </button>
        {MAPS.filter(([id]) => open || id === s.layer).map(([id, label, icon]) => (
          <button key={id} className={`item ${s.layer === id ? 'on' : ''}`} onClick={() => s.set({ layer: id, sens: null })}>
            {icon}<span>{label}</span>
          </button>
        ))}
        {open && (
          <>
            <h5>Universes</h5>
            <button className={`item ${s.drawer === 'shock' ? 'on' : ''}`} onClick={() => s.set({ drawer: s.drawer === 'shock' ? null : 'shock' })}>
              <IconFork /><span>Fork a universe</span>
            </button>
            {forked && (
              <div className="subs">
                {check('Difference', s.delta, () => s.set({ delta: !s.delta, compare: false }), false, 'Universe minus control')}
                {check('Swipe compare', s.compare, () => s.set({ compare: !s.compare, delta: false }), false, 'Control on the left, universe on the right')}
                {check('Beyond error', s.showStipple, () => s.set({ showStipple: !s.showStipple }), !s.delta, 'Dots where the change exceeds the measured forecast error (needs Difference)')}
              </div>
            )}
            <button className={`item ${s.drawer === 'audit' ? 'on' : ''}`} onClick={() => s.set({ drawer: s.drawer === 'audit' ? null : 'audit' })}>
              <IconShield /><span>Audit</span>
            </button>
          </>
        )}
      </nav>
    </>
  )
}
