import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { CITIES } from '../../lib/cities'
import { NEXT_PRESS, NEXT_TEMP, NEXT_WIND, pressLabel, tempLabel, windLabel } from '../../lib/units'
import type { RailPanel, Tab } from '../../state/store'
import { useStore } from '../../state/store'
import { useMap } from '../../state/mapctl'
import {
  IconClose, IconDots, IconDraw, IconGear, IconInfo, IconIsobars, IconLocate, IconMinus, IconParticles, IconPlus, IconRing, IconSearch, Mark,
} from '../icons'

interface BtnProps { tip: string; on?: boolean; disabled?: boolean; onClick: () => void; children: ReactNode }
/** Round 40 px map button with a tooltip on the left. */
const Btn = ({ tip, on = false, disabled = false, onClick, children }: BtnProps) => (
  <button className={`rb ${on ? 'on' : ''}`} data-tip={tip} aria-label={tip} aria-pressed={on} disabled={disabled} onClick={onClick}>{children}</button>
)

/** Right edge: map tools as round buttons, overlay toggles and zoom at the bottom, popover panels to their left. */
export function Rail() {
  const s = useStore()
  const zoomBy = useMap((m) => m.zoomBy)
  const fit = useMap((m) => m.fit)
  const tog = (p: RailPanel) => s.set({ panel: s.panel === p ? null : p })
  return (
    <>
      <div className="rail top" data-ui>
        <Btn tip="Search" on={s.panel === 'search'} onClick={() => tog('search')}><IconSearch /></Btn>
        <Btn tip="Settings" on={s.panel === 'settings'} onClick={() => tog('settings')}><IconGear /></Btn>
        <Btn tip="About, validation and more" on={s.panel === 'info'} onClick={() => tog('info')}><IconInfo /></Btn>
        <div className="cap">
          <Btn tip="Draw a shock" on={s.drawMode} onClick={() => s.set({ drawMode: !s.drawMode, drawer: 'shock' })}><IconDraw /></Btn>
          <Btn tip="Speed-limit rings" on={s.showRings} onClick={() => s.set({ showRings: !s.showRings })}><IconRing /></Btn>
        </div>
        <Btn tip="Show the whole model domain" onClick={fit}><IconLocate /></Btn>
      </div>
      <div className="rail bottom" data-ui>
        <div className="cap">
          <Btn tip="Wind particles" on={s.showParticles} onClick={() => s.set({ showParticles: !s.showParticles })}><IconParticles /></Btn>
          <Btn tip="Pressure lines" on={s.showIsobars} onClick={() => s.set({ showIsobars: !s.showIsobars })}><IconIsobars /></Btn>
          <Btn tip="More settings" on={s.panel === 'settings'} onClick={() => tog('settings')}><IconDots /></Btn>
        </div>
        <div className="cap">
          <Btn tip="Zoom in" onClick={() => zoomBy(1.5)}><IconPlus /></Btn>
          <Btn tip="Zoom out" onClick={() => zoomBy(1 / 1.5)}><IconMinus /></Btn>
        </div>
      </div>
      {s.panel === 'search' && <SearchPanel />}
      {s.panel === 'settings' && <SettingsPanel />}
      {s.panel === 'info' && <InfoPanel />}
    </>
  )
}

function PopHead({ title }: { title: string }) {
  const set = useStore((s) => s.set)
  return (
    <header className="pophead">
      <h3>{title}</h3>
      <button className="x" onClick={() => set({ panel: null })} aria-label="Close"><IconClose /></button>
    </header>
  )
}

function SearchPanel() {
  const s = useStore()
  const [q, setQ] = useState('')
  const hits = useMemo(() => {
    const k = q.trim().toLowerCase()
    const places = CITIES.filter((c) => !k || c.name.toLowerCase().includes(k)).slice(0, k ? 8 : 6)
    const wins = s.windows.filter((w) => !k || w.label.toLowerCase().includes(k))
    return { places, wins }
  }, [q, s.windows])
  const go = (lat: number, lon: number) => s.set({ focus: { lat, lon, zoom: 2.4, seq: Date.now() }, pin: { lat, lon }, sens: null, panel: null })
  return (
    <section className="pop panel search" data-ui>
      <form onSubmit={(e) => { e.preventDefault(); if (hits.places[0]) go(hits.places[0].lat, hits.places[0].lon) }}>
        <IconSearch />
        <input type="search" autoFocus placeholder="Search places and start states" value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Escape') s.set({ panel: null }) }} />
      </form>
      <div className="results">
        {hits.places.length > 0 && <h5>Places</h5>}
        {hits.places.map((c) => (
          <button key={c.name} onClick={() => go(c.lat, c.lon)}><span className="pinic" />{c.name}<small>{c.lat.toFixed(1)}° N, {c.lon.toFixed(1)}° E</small></button>
        ))}
        {hits.wins.length > 0 && <h5>Start states</h5>}
        {hits.wins.map((w) => (
          <button key={w.id} className={w.id === s.windowId ? 'on' : ''} onClick={() => { void s.selectWindow(w.id); s.set({ panel: null }) }}>
            <span className="calic" />{w.label}<small>{w.season}</small>
          </button>
        ))}
        {!hits.places.length && !hits.wins.length && <p className="none">No match. The map covers 6–38° N, 65–101° E.</p>}
      </div>
    </section>
  )
}

function SettingsPanel() {
  const s = useStore()
  return (
    <section className="pop panel" data-ui>
      <PopHead title="Settings" />
      <h5>Start state</h5>
      <div className="list">{s.windows.map((w) => (
        <button key={w.id} className={`row ${w.id === s.windowId ? 'on' : ''}`} onClick={() => void s.selectWindow(w.id)}>{w.label}<small>{w.season}</small></button>
      ))}</div>
      <h5>Units</h5>
      <div className="list">
        <button className="row" onClick={() => s.setUnits({ temp: NEXT_TEMP[s.units.temp] })}>Temperature <b>{tempLabel(s.units.temp)}</b></button>
        <button className="row" onClick={() => s.setUnits({ wind: NEXT_WIND[s.units.wind] })}>Wind <b>{windLabel(s.units.wind)}</b></button>
        <button className="row" onClick={() => s.setUnits({ press: NEXT_PRESS[s.units.press] })}>Pressure <b>{pressLabel(s.units.press)}</b></button>
      </div>
      <h5>Playback</h5>
      <div className="seg3">{[0.5, 1, 2].map((v) => <button key={v} className={s.speed === v ? 'on' : ''} onClick={() => s.set({ speed: v })}>{v}×</button>)}</div>
      <h5>Status</h5>
      <p className="status">
        <i className={s.judgeOnline ? 'ok' : 'bad'} />Forecast server {s.judgeOnline ? 'ready' : 'offline'}<br />
        <i className={s.labOnline ? 'ok' : 'bad'} />Lab server {s.labOnline ? 'online' : 'offline'}<br />
        <span>{s.meta?.model_name}</span>
      </p>
    </section>
  )
}

const VIEWS: [Tab, string, string][] = [
  ['timeline', 'Timeline Prime', 'Forecast against what happened'],
  ['validation', 'Validation', 'Skill, causality and stress tests'],
  ['about', 'About the model', 'How it works and its limits'],
]

function InfoPanel() {
  const s = useStore()
  return (
    <section className="pop panel info" data-ui>
      <PopHead title="Wethrfork" />
      <div className="brandrow"><Mark size={40} /><p>A 10-day forecast for South Asia with a speed limit: fork the weather, watch the change spread no faster than the physics allows.</p></div>
      <nav className="list">{VIEWS.map(([id, label, sub]) => (
        <button key={id} className="row nav" onClick={() => s.set({ tab: id, panel: null, playing: false })}><span><b>{label}</b><small>{sub}</small></span><i>›</i></button>
      ))}</nav>
      <p className="fine">Forecast data: our model, started from ERA5 (C3S) via WeatherBench 2. Imagery: NASA Blue Marble. Borders: Natural Earth. Works offline.</p>
    </section>
  )
}
