import { useMemo, useState } from 'react'
import { FieldMap, useOutline } from '../FieldMap'
import { LAYER_ORDER, LAYERS, scalarAt } from '../../lib/layers'
import type { LayerId } from '../../lib/layers'
import { CELLS } from '../../lib/grid'
import { skillByDay } from '../../lib/stats'
import { tempDelta } from '../../lib/units'
import { CONTROL, useStore } from '../../state/store'

const W = 560, H = 210

export function TimelinePrime() {
  const { universes, truth, init, clim, layer: mapLayer, units, windows, windowId } = useStore()
  const [layer, setLayer] = useState<LayerId>(mapLayer)
  const [day, setDay] = useState(3)
  const outline = useOutline()
  const model = universes[CONTROL]?.rollout ?? null
  const def = LAYERS[layer]
  const rows = useMemo(() => (model && truth && init ? skillByDay(model, truth, init, clim, layer) : null), [model, truth, init, clim, layer])
  const fields = useMemo(() => {
    if (!model || !truth) return null
    const m = scalarAt(model, day, layer, new Float32Array(CELLS)), t = scalarAt(truth, day, layer, new Float32Array(CELLS))
    const e = new Float32Array(CELLS)
    let big = 0
    for (let i = 0; i < CELLS; i++) { e[i] = m[i] - t[i]; big = Math.max(big, Math.abs(e[i])) }
    return { m, t, e, emax: Math.max(big * 0.8, def.deltaFloor) }
  }, [model, truth, day, layer, def.deltaFloor])
  const label = windows.find((w) => w.id === windowId)?.label ?? ''
  if (!model) return <div className="page"><p className="hint">Loading the control run…</p></div>
  if (!truth) return <div className="page"><h2>Timeline Prime</h2><p className="hint">This start state has no held-out truth. Pick a window labelled “held out”.</p></div>

  const maxY = rows ? Math.max(...rows.flatMap((r) => [r.model, r.persist, r.clim ?? 0])) * 1.1 : 1
  const sx = (d: number) => 44 + (d / 9) * (W - 60), sy = (v: number) => H - 28 - (v / maxY) * (H - 44)
  const line = (key: 'model' | 'persist' | 'clim') => rows!.map((r, d) => (r[key] === null ? '' : `${sx(d)},${sy(r[key] as number)}`)).filter(Boolean).join(' ')
  const unitConv = (v: number) => (layer === 'temp' ? tempDelta(v, units.temp) : def.disp(v, units)) // errors are differences

  return (
    <div className="page">
      <div className="pagehead">
        <div><h2>Timeline Prime</h2><p>The model against what actually happened. {label}. Nothing here is tuned to this window.</p></div>
        <div className="pillrow">
          {LAYER_ORDER.map((id) => <button key={id} className={layer === id ? 'on' : ''} onClick={() => setLayer(id)}>{LAYERS[id].label}</button>)}
        </div>
      </div>
      <div className="maps3">
        <FieldMap data={fields?.t ?? null} layer={def} title="Reality (reanalysis)" outline={outline} />
        <FieldMap data={fields?.m ?? null} layer={def} title="Wethrfork forecast" outline={outline} />
        <FieldMap data={fields?.e ?? null} layer={def} dmax={fields?.emax ?? 1} title="Error (forecast − reality)" note={`scale ±${unitConv(fields?.emax ?? 0).toFixed(1)} ${def.unit(units)}`} outline={outline} />
      </div>
      <div className="scrubrow">
        <span>Day +{day + 1}</span>
        <input type="range" min={0} max={9} value={day} onChange={(e) => setDay(+e.target.value)} />
      </div>
      <div className="cards2">
        <section className="card">
          <h3>Error by lead · {def.label}</h3>
          {rows && (
            <svg viewBox={`0 0 ${W} ${H}`} className="chart">
              {[0, 0.25, 0.5, 0.75, 1].map((f) => <g key={f}><line x1={44} x2={W - 16} y1={sy(maxY * f / 1.1)} y2={sy(maxY * f / 1.1)} stroke="rgba(255,255,255,0.08)" /><text x={38} y={sy(maxY * f / 1.1) + 3} textAnchor="end">{unitConv((maxY * f) / 1.1).toFixed(layer === 'pressure' ? 1 : 2)}</text></g>)}
              {rows.map((r, d) => <text key={d} x={sx(d)} y={H - 10} textAnchor="middle">+{r.day}</text>)}
              <polyline points={line('persist')} className="l-persist" />
              {rows[0].clim !== null && <polyline points={line('clim')} className="l-clim" />}
              <polyline points={line('model')} className="l-model" />
              <circle cx={sx(day)} cy={sy(rows[day].model)} r={4.5} fill="#4cc2ff" />
            </svg>
          )}
          <div className="plegend"><span><i style={{ background: '#4cc2ff' }} />Wethrfork</span><span><i style={{ background: '#ff8a65' }} />persistence</span><span><i style={{ background: '#9fb3c8' }} />climatology</span></div>
          <small className="dim">RMSE in {def.unit(units)}, latitude-weighted.</small>
        </section>
        <section className="card">
          <h3>Skill against the best reference</h3>
          <table className="skill"><thead><tr><th>Day</th><th>Forecast</th><th>Persistence</th><th>Climatology</th><th>Skill</th></tr></thead>
            <tbody>{rows?.map((r) => <tr key={r.day} className={r.day === day + 1 ? 'cur' : ''}><td>+{r.day}</td><td>{unitConv(r.model).toFixed(2)}</td><td>{unitConv(r.persist).toFixed(2)}</td><td>{r.clim === null ? '–' : unitConv(r.clim).toFixed(2)}</td><td className={r.skill >= 0 ? 'ok' : 'bad'}>{(r.skill * 100).toFixed(0)}%</td></tr>)}</tbody></table>
          <small className="dim">Skill = 1 − RMSE ÷ the better of persistence and climatology, like the organisers&rsquo; score. Positive means we beat both.</small>
        </section>
      </div>
    </div>
  )
}
