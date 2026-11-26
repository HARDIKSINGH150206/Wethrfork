import { useState } from 'react'
import { IconGear } from './icons'
import type { Tab } from '../state/store'
import { useStore } from '../state/store'
import { NEXT_PRESS, NEXT_TEMP, NEXT_WIND, pressLabel, tempLabel, windLabel } from '../lib/units'

const TABS: [Tab, string][] = [['map', 'Map'], ['timeline', 'Timeline Prime'], ['validation', 'Validation'], ['about', 'About']]

export function TopBar() {
  const { tab, set, windows, windowId, selectWindow, judgeOnline, labOnline, meta, units, setUnits } = useStore()
  const [open, setOpen] = useState(false)
  return (
    <header className="top" data-ui>
      <div className="brand">
        <svg width="26" height="26" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#4cc2ff" /><path d="M7 10l4 12 5-9 5 9 4-12" stroke="#06121c" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
        <div><b>WETHRFORK</b><small>a weather model with a speed limit</small></div>
      </div>
      <nav>{TABS.map(([id, label]) => <button key={id} className={tab === id ? 'on' : ''} onClick={() => set({ tab: id, playing: false })}>{label}</button>)}</nav>
      <div className="right">
        <label className="win">
          <span>Start state</span>
          <select value={windowId ?? ''} onChange={(e) => selectWindow(e.target.value)}>
            {windows.map((w) => <option key={w.id} value={w.id}>{w.label}</option>)}
          </select>
        </label>
        <span className={`badge ${judgeOnline ? 'on' : 'off'}`}>server {judgeOnline ? 'ready' : 'offline'}</span>
        <span className={`badge ${labOnline ? 'on' : 'off'}`}>lab {labOnline ? 'online' : 'offline'}</span>
        {meta && <span className="badge">{meta.model_name.replace('wethrfork-', '')}</span>}
        <div className="gear">
          <button onClick={() => setOpen(!open)} aria-label="Units"><IconGear /></button>
          {open && (
            <div className="unitsmenu" onMouseLeave={() => setOpen(false)}>
              <button onClick={() => setUnits({ temp: NEXT_TEMP[units.temp] })}>Temperature <b>{tempLabel(units.temp)}</b></button>
              <button onClick={() => setUnits({ wind: NEXT_WIND[units.wind] })}>Wind <b>{windLabel(units.wind)}</b></button>
              <button onClick={() => setUnits({ press: NEXT_PRESS[units.press] })}>Pressure <b>{pressLabel(units.press)}</b></button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
