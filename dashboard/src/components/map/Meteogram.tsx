import { useMemo, useState } from 'react'
import { CELLS } from '../../lib/grid'
import { sample } from '../../lib/interp'
import { scalarAt, windAt } from '../../lib/layers'
import { dayName, placeName } from '../../lib/dates'
import { pressLabel, pressOf, tempLabel, tempOf, windLabel, windOf } from '../../lib/units'
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
  const { pin, universes, selected, units, tf, set, doy, weekday } = useStore()
  const [mode, setMode] = useState<'basic' | 'chart'>('basic')
  const sel = universes[selected]?.rollout, ctl = universes[CONTROL]?.rollout
  const data = useMemo(() => (pin && sel ? rows(sel, pin.lat, pin.lon) : null), [pin, sel])
  const base = useMemo(() => (pin && ctl && selected !== CONTROL ? rows(ctl, pin.lat, pin.lon) : null), [pin, ctl, selected])
  if (!pin || !data) return null
  const day = Math.round(tf)
  const maxR = Math.max(5, ...data.map((d) => d.r), ...(base ?? []).map((d) => d.r))
  const diff = (a: number, b: number | undefined, f: (x: number) => number, digits = 1) =>
    b === undefined ? null : <small className={a - b >= 0 ? 'up' : 'down'}>{a - b >= 0 ? '+' : ''}{(f(a) - f(b)).toFixed(digits)}</small>
  return (
    <section className="meteo panel" data-ui onPointerDown={(e) => e.stopPropagation()}>
      <header>
        <b>{placeName(pin.lat, pin.lon)}</b>
        <span>{placeName(pin.lat, pin.lon).includes('°') ? '' : `${pin.lat.toFixed(2)}°N ${pin.lon.toFixed(2)}°E · `}{universes[selected]?.name}{base ? ' vs control' : ''}</span>
        <div className="mtabs">
          <button className={mode === 'basic' ? 'on' : ''} onClick={() => setMode('basic')}>Basic</button>
          <button className={mode === 'chart' ? 'on' : ''} onClick={() => setMode('chart')}>Meteogram</button>
        </div>
        <button onClick={() => set({ meteo: false })} aria-label="Close">×</button>
      </header>
      {mode === 'chart' ? <Chart data={data} base={base} day={day} units={units} labels={data.map((_, d) => dayName(doy, d + 1, weekday, true))} onDay={(d) => set({ tf: d })} /> : (
      <table>
        <tbody>
          <tr className="days"><th />{data.map((_, d) => <td key={d} className={d === day ? 'cur' : ''} onClick={() => set({ tf: d })}>{dayName(doy, d + 1, weekday, true)}<small>+{d + 1} d</small></td>)}</tr>
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
      )}
    </section>
  )
}

type Row = ReturnType<typeof rows>[number]
interface ChartProps { data: Row[]; base: Row[] | null; day: number; units: import('../../lib/units').Units; labels: string[]; onDay: (d: number) => void }

/** Meteogram: temperature and pressure lines over rain bars, universe solid, control dashed. */
function Chart({ data, base, day, units, labels, onDay }: ChartProps) {
  const W = 1200, H = 230, L = 60, R = 60, T = 14, B = 34
  const x = (d: number) => L + ((d + 0.5) / 10) * (W - L - R)
  const temps = [...data, ...(base ?? [])].map((r) => tempOf(r.t, units.temp))
  const tLo = Math.floor(Math.min(...temps) - 1), tHi = Math.ceil(Math.max(...temps) + 1)
  const yT = (v: number) => T + (1 - (v - tLo) / (tHi - tLo || 1)) * (H - T - B) * 0.62
  const pr = [...data, ...(base ?? [])].map((r) => pressOf(r.p, units.press))
  const pLo = Math.min(...pr) - 1, pHi = Math.max(...pr) + 1
  const yP = (v: number) => T + (1 - (v - pLo) / (pHi - pLo || 1)) * (H - T - B) * 0.62
  const rMax = Math.max(10, ...data.map((r) => r.r), ...(base ?? []).map((r) => r.r))
  const rainTop = T + (H - T - B) * 0.66
  const yR = (v: number) => H - B - (v / rMax) * (H - B - rainTop)
  const path = (rs: Row[], f: (r: Row) => number) => rs.map((r, d) => `${d ? 'L' : 'M'}${x(d)},${f(r)}`).join(' ')
  const bw = (W - L - R) / 10
  return (
    <svg className="mchart" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      {data.map((_, d) => <rect key={d} x={L + d * bw} y={T} width={bw} height={H - T - B} className={d === day ? 'colcur' : d % 2 ? 'colodd' : 'col'} onClick={() => onDay(d)} />)}
      {data.map((r, d) => <rect key={'r' + d} x={x(d) - bw * 0.18} y={yR(r.r)} width={bw * 0.36} height={H - B - yR(r.r)} className="mrain" />)}
      {data.map((r, d) => <text key={'rt' + d} x={x(d)} y={yR(r.r) - 3} className="mrt">{r.r >= 0.1 ? r.r.toFixed(1) : ''}</text>)}
      {base && <path d={path(base, (r) => yP(pressOf(r.p, units.press)))} className="mpress ctl" />}
      <path d={path(data, (r) => yP(pressOf(r.p, units.press)))} className="mpress" />
      {base && <path d={path(base, (r) => yT(tempOf(r.t, units.temp)))} className="mtemp ctl" />}
      <path d={path(data, (r) => yT(tempOf(r.t, units.temp)))} className="mtemp" />
      {data.map((r, d) => <text key={'t' + d} x={x(d)} y={yT(tempOf(r.t, units.temp)) - 8} className="mtt">{tempOf(r.t, units.temp).toFixed(0)}°</text>)}
      {labels.map((l, d) => <text key={'l' + d} x={x(d)} y={H - 12} className="mlab">{l}</text>)}
      <text x={8} y={T + 10} className="maxis">{tempLabel(units.temp)}</text>
      <text x={W - 8} y={T + 10} className="maxis r">{pressLabel(units.press)}</text>
      <text x={8} y={H - B - 4} className="maxis">rain mm</text>
    </svg>
  )
}
