import { useMemo, useState } from 'react'
import { CITIES } from '../../lib/cities'
import type { Tab } from '../../state/store'
import { useStore } from '../../state/store'
import { NEXT_PRESS, NEXT_TEMP, NEXT_WIND, pressLabel, tempLabel, windLabel } from '../../lib/units'
import { IconBolt } from '../icons'

const VIEWS: [Tab, string, string][] = [
  ['map', 'Map', 'Forecast and forks'],
  ['timeline', 'Timeline Prime', 'Forecast against reality'],
  ['validation', 'Validation', 'Skill, causality, stress tests'],
  ['about', 'About', 'How the model works'],
]

/** Top-left: menu button, location search and the fork button, like the search corner of a weather map. */
export function TopLeft() {
  const s = useStore()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const hits = useMemo(() => {
    const k = q.trim().toLowerCase()
    const places = CITIES.filter((c) => !k || c.name.toLowerCase().includes(k)).slice(0, k ? 8 : 6)
    const wins = s.windows.filter((w) => !k || w.label.toLowerCase().includes(k))
    return { places, wins }
  }, [q, s.windows])
  const go = (lat: number, lon: number) => {
    s.set({ focus: { lat, lon, zoom: 2.4, seq: Date.now() }, pin: { lat, lon }, sens: null })
    setOpen(false); setQ('')
  }
  return (
    <>
      <div className="tl" data-ui>
        <button className="burger" onClick={() => s.set({ menuOpen: !s.menuOpen })} aria-label="Menu"><span /><span /><span /></button>
        <div className={`search ${open ? 'open' : ''}`}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
          <input placeholder="Search location…" value={q} onFocus={() => setOpen(true)} onChange={(e) => { setQ(e.target.value); setOpen(true) }}
            onKeyDown={(e) => { if (e.key === 'Enter' && hits.places[0]) go(hits.places[0].lat, hits.places[0].lon); if (e.key === 'Escape') setOpen(false) }} />
          {open && (
            <div className="results" onMouseLeave={() => setOpen(false)}>
              {hits.places.map((c) => <button key={c.name} onClick={() => go(c.lat, c.lon)}><span className="pinic" />{c.name}<small>{c.lat.toFixed(1)}°N {c.lon.toFixed(1)}°E</small></button>)}
              {hits.wins.length > 0 && <div className="rhead">Start state</div>}
              {hits.wins.map((w) => (
                <button key={w.id} className={w.id === s.windowId ? 'on' : ''} onClick={() => { void s.selectWindow(w.id); setOpen(false) }}>
                  <span className="calic" />{w.label}<small>{w.season}</small>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      <button className={`forkbtn ${s.drawer ? 'on' : ''}`} data-ui onClick={() => s.set({ drawer: s.drawer ? null : 'shock' })}>
        <IconBolt /> Fork a universe
      </button>
      {s.menuOpen && (
        <aside className="menu" data-ui>
          <header>
            <svg width="28" height="28" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#e0e0e0" /><path d="M7 10l4 12 5-9 5 9 4-12" stroke="#2b2b2b" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
            <div><b>Wethrfork</b><small>a weather model with a speed limit</small></div>
            <button className="x" onClick={() => s.set({ menuOpen: false })} aria-label="Close">×</button>
          </header>
          <nav>{VIEWS.map(([id, label, sub]) => (
            <button key={id} className={s.tab === id ? 'on' : ''} onClick={() => s.set({ tab: id, menuOpen: false, playing: false })}><b>{label}</b><small>{sub}</small></button>
          ))}</nav>
          <h4>Start state</h4>
          <div className="wins">{s.windows.map((w) => (
            <button key={w.id} className={w.id === s.windowId ? 'on' : ''} onClick={() => void s.selectWindow(w.id)}>{w.label}</button>
          ))}</div>
          <h4>Units</h4>
          <div className="units">
            <button onClick={() => s.setUnits({ temp: NEXT_TEMP[s.units.temp] })}>Temperature <b>{tempLabel(s.units.temp)}</b></button>
            <button onClick={() => s.setUnits({ wind: NEXT_WIND[s.units.wind] })}>Wind <b>{windLabel(s.units.wind)}</b></button>
            <button onClick={() => s.setUnits({ press: NEXT_PRESS[s.units.press] })}>Pressure <b>{pressLabel(s.units.press)}</b></button>
          </div>
          <h4>Status</h4>
          <p className="status"><i className={s.judgeOnline ? 'ok' : 'bad'} /> forecast server {s.judgeOnline ? 'ready' : 'offline'}<br /><i className={s.labOnline ? 'ok' : 'bad'} /> lab server {s.labOnline ? 'online' : 'offline'}<br /><span>{s.meta?.model_name}</span></p>
        </aside>
      )}
    </>
  )
}
