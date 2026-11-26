import { useMemo } from 'react'
import { CELLS } from '../../lib/grid'
import { sample } from '../../lib/interp'
import { scalarAt, windAt } from '../../lib/layers'
import { dayLabel, placeName } from '../../lib/dates'
import { pressOf, pressLabel, tempLabel, tempOf, windLabel, windOf } from '../../lib/units'
import { CONTROL, useStore } from '../../state/store'

const U = new Float32Array(CELLS), V = new Float32Array(CELLS)

function rows(roll: Float32Array, lat: number, lon: number) {
  const out = []
  for (let d = 0; d < 10; d++) {
    windAt(roll, d, U, V)
    const u = sample(U, lat, lon), v = sample(V, lat, lon)
    out.push({
      t: sample(scalarAt(roll, d, 'temp'), lat, lon),
      r: sample(scalarAt(roll, d, 'rain'), lat, lon),
      w: Math.hypot(u, v),
      dir: ((Math.atan2(-u, -v) * 180) / Math.PI + 360) % 360,
      p: sample(scalarAt(roll, d, 'pressure'), lat, lon),
      q: sample(scalarAt(roll, d, 'moisture'), lat, lon),
    })
  }
  return out
}

const tempColor = (c: number) => `hsl(${Math.max(Math.min(220 - (c + 5) * 5.2, 260), 0)} 55% 42%)`

/** Windy-style detailed forecast for the pinned point: one column per day, selected universe against control. */
export function Meteogram() {
  const { pin, universes, selected, units, tf, set, doy } = useStore()
  const sel = universes[selected]?.rollout, ctl = universes[CONTROL]?.rollout
  const data = useMemo(() => (pin && sel ? rows(sel, pin.lat, pin.lon) : null), [pin, sel])
  const base = useMemo(() => (pin && ctl && selected !== CONTROL ? rows(ctl, pin.lat, pin.lon) : null), [pin, ctl, selected])
  if (!pin || !data) return null
  const day = Math.round(tf)
  const maxR = Math.max(5, ...data.map((d) => d.r), ...(base ?? []).map((d) => d.r))
  const diff = (a: number, b: number | undefined, f: (x: number) => number, digits = 1) =>
    b === undefined ? null : <small className={a - b >= 0 ? 'up' : 'down'}>{a - b >= 0 ? '+' : ''}{(f(a) - f(b)).toFixed(digits)}</small>
  return (
    <section className="meteo" data-ui onPointerDown={(e) => e.stopPropagation()}>
      <header>
        <b>{placeName(pin.lat, pin.lon)}</b>
        <span>{pin.lat.toFixed(2)}°N {pin.lon.toFixed(2)}°E · {universes[selected]?.name}{base ? ' vs control' : ''}</span>
        <button onClick={() => set({ meteo: false })} aria-label="Close">×</button>
      </header>
      <table>
        <tbody>
          <tr className="days"><th />{data.map((_, d) => <td key={d} className={d === day ? 'cur' : ''} onClick={() => set({ tf: d })}>{dayLabel(doy, d + 1)}<small>+{d + 1}</small></td>)}</tr>
          <tr><th>Temperature <small>{tempLabel(units.temp)}</small></th>{data.map((r, d) => (
            <td key={d} className={d === day ? 'cur' : ''}><span className="chip" style={{ background: tempColor(r.t - 273.15) }}>{tempOf(r.t, units.temp).toFixed(0)}°</span>{diff(r.t, base?.[d].t, (x) => tempOf(x, units.temp))}</td>))}</tr>
          <tr><th>Rain <small>mm</small></th>{data.map((r, d) => (
            <td key={d} className={d === day ? 'cur' : ''}><div className="rbar"><i style={{ height: `${(r.r / maxR) * 100}%` }} /></div>{r.r >= 0.1 ? r.r.toFixed(1) : '·'}{diff(r.r, base?.[d].r, (x) => x)}</td>))}</tr>
          <tr><th>Wind <small>{windLabel(units.wind)}</small></th>{data.map((r, d) => (
            <td key={d} className={d === day ? 'cur' : ''}><span className="warr" style={{ transform: `rotate(${r.dir + 180}deg)` }}>↑</span>{windOf(r.w, units.wind).toFixed(0)}{diff(r.w, base?.[d].w, (x) => windOf(x, units.wind))}</td>))}</tr>
          <tr><th>Pressure <small>{pressLabel(units.press)}</small></th>{data.map((r, d) => (
            <td key={d} className={d === day ? 'cur' : ''}>{pressOf(r.p, units.press).toFixed(0)}{diff(r.p, base?.[d].p, (x) => pressOf(x, units.press))}</td>))}</tr>
          <tr><th>Moisture <small>kg/m²</small></th>{data.map((r, d) => (
            <td key={d} className={d === day ? 'cur' : ''}>{r.q.toFixed(0)}{diff(r.q, base?.[d].q, (x) => x)}</td>))}</tr>
        </tbody>
      </table>
    </section>
  )
}
