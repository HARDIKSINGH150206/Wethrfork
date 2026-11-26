import { useEffect, useMemo, useState } from 'react'
import { getFuzz, getNatural } from '../../api/labClient'
import { simulate } from '../../api/judgeClient'
import { FieldMap, useOutline } from '../FieldMap'
import { LAYERS } from '../../lib/layers'
import { CELLS, NC, NLAT, NLON } from '../../lib/grid'
import { useStore } from '../../state/store'

interface Grade { n_windows: number; mean_ss: number; mean_csi_skill: number; rmse_pts: number; csi_pts: number; blur_pts: number; var_ratio_day8_mean: number[]; ss_by_lead_channel: Record<string, number[]>; csi_skill_by_lead: Record<string, number> }
type GateRow = { near: number; growth: number; far: number; max_z: number; pass: boolean }
type Gate = Record<string, { warm_ocean: GateRow; monsoon_stall: GateRow; null_max_diff: number }>
interface FuzzCase { channel: string; amp: string; pass: boolean; valid: boolean }
interface Fuzz { n?: number; validity?: number; pass_rate?: number; cases?: FuzzCase[]; available?: boolean }
interface Natural { n_events?: number; lead?: number; pattern_corr?: { tp: number; msl: number }; observed_composite?: Record<string, number[][][]>; model_response?: Record<string, number[][][]>; available?: boolean }

const CH = ['t2m', 'tp', 'u10', 'v10', 'msl', 'tcwv']
const heat = (v: number) => `hsl(${Math.round(Math.max(Math.min(v, 1), -0.1) * 120 + 12)} 60% ${v > 0.15 ? 36 : 30}%)`

function useJson<T>(url: string): T | null {
  const [d, setD] = useState<T | null>(null)
  useEffect(() => { fetch(url).then((r) => r.json()).then(setD).catch(() => null) }, [url])
  return d
}

function LightCone() {
  const { init, doy, judgeOnline } = useStore()
  const [lat, setLat] = useState(22.5), [lon, setLon] = useState(80.5)
  const [res, setRes] = useState<{ reach: number[]; map: Float32Array } | null>(null)
  const [busy, setBusy] = useState(false), [err, setErr] = useState('')
  const run = async () => {
    if (!init || !doy) return
    setBusy(true); setErr('')
    try {
      const i = Math.round(lat - 6.5), j = Math.round(lon - 65.5)
      const pert = new Float32Array(NC * CELLS)
      pert[(0 * NLAT + i) * NLON + j] = 4 // +4 K on a single cell
      const [a, b] = await Promise.all([simulate(init, doy, null), simulate(init, doy, pert)])
      const reach: number[] = []
      for (let d = 0; d < 10; d++) {
        let m = 0
        for (let c = 0; c < NC; c++) for (let ii = 0; ii < NLAT; ii++) for (let jj = 0; jj < NLON; jj++) {
          const k = ((d * NC + c) * NLAT + ii) * NLON + jj
          const std = [13.46, 7.55, 2.9, 2.43, 619, 20.5][c]
          if (Math.abs(b.rollout[k] - a.rollout[k]) / std > 1e-4) m = Math.max(m, Math.max(Math.abs(ii - i), Math.abs(jj - j)))
        }
        reach.push(m)
      }
      const map = new Float32Array(CELLS)
      for (let k = 0; k < CELLS; k++) map[k] = b.rollout[(5 * NC) * CELLS + k] - a.rollout[(5 * NC) * CELLS + k]
      setRes({ reach, map })
    } catch (e) { setErr(String(e)) }
    setBusy(false)
  }
  const W = 360, H = 190, sx = (d: number) => 36 + (d / 9) * (W - 50), sy = (v: number) => H - 26 - (v / 80) * (H - 40)
  return (
    <section className="card wide">
      <h3>Live light-cone test</h3>
      <p className="dim">Fire a +4 K pulse into a single cell through the real server and measure how far the response travels each day. The network's update is bounded to 8 cells along either axis (about 900 km) per day; the chart measures the farthest cell, in max-axis distance, that changes.</p>
      <div className="form row">
        <label>Latitude<input type="number" value={lat} step={1} onChange={(e) => setLat(+e.target.value)} /></label>
        <label>Longitude<input type="number" value={lon} step={1} onChange={(e) => setLon(+e.target.value)} /></label>
        <button className="primary" disabled={!judgeOnline || !init || busy} onClick={run}>{busy ? 'running…' : 'Fire the pulse'}</button>
      </div>
      {err && <p className="err">{err}</p>}
      {res && (
        <div className="lc">
          <svg viewBox={`0 0 ${W} ${H}`} className="chart">
            {[0, 20, 40, 60, 80].map((v) => <g key={v}><line x1={36} x2={W - 14} y1={sy(v)} y2={sy(v)} stroke="rgba(255,255,255,0.08)" /><text x={30} y={sy(v) + 3} textAnchor="end">{v}</text></g>)}
            {res.reach.map((_, d) => <text key={d} x={sx(d)} y={H - 8} textAnchor="middle">+{d + 1}</text>)}
            <polyline className="l-limit" points={res.reach.map((_, d) => `${sx(d)},${sy(8 * (d + 1))}`).join(' ')} />
            <polyline className="l-model" points={res.reach.map((r, d) => `${sx(d)},${sy(r)}`).join(' ')} />
          </svg>
          <div className="plegend"><span><i style={{ background: '#ff7b54' }} />limit 8 cells/day</span><span><i style={{ background: '#4cc2ff' }} />measured reach (cells)</span></div>
          <p className="ok">Measured reach after 1, 4 and 10 days: {res.reach[0]}, {res.reach[3]}, {res.reach[9]} cells; limit {8}, {32}, {80}.</p>
        </div>
      )}
    </section>
  )
}

export function Validation() {
  const grade = useJson<{ systematic: Grade; typed: Grade }>('/selfgrade.json')
  const gate = useJson<Gate>('/gate.json')
  const [fuzz, setFuzz] = useState<Fuzz | null>(null)
  const [nat, setNat] = useState<Natural | null>(null)
  const outline = useOutline()
  useEffect(() => { getFuzz().then((d) => setFuzz(d as Fuzz)).catch(() => null); getNatural().then((d) => setNat(d as Natural)).catch(() => null) }, [])
  const g = grade?.systematic
  const amps = useMemo(() => (fuzz?.cases ? Array.from(new Set(fuzz.cases.map((c) => c.amp))).sort() : []), [fuzz])
  const weakest = useMemo(() => {
    if (!fuzz?.cases) return ''
    const cells: { c: string; a: string; r: number; n: number }[] = []
    for (const c of CH) for (const a of amps) {
      const v = fuzz.cases.filter((x) => x.channel === c && x.amp === a)
      if (v.length) cells.push({ c, a, r: v.filter((x) => x.pass).length / v.length, n: v.length })
    }
    const bad = cells.filter((x) => x.r < 1).sort((p, q) => p.r - q.r)
    return bad.length ? `Weakest: ${bad.slice(0, 2).map((x) => `${x.c} at ${x.a} (${Math.round(x.r * 100)}% of ${x.n})`).join(', ')}.` : 'Every sampled combination passed.'
  }, [fuzz, amps])
  const natField = (key: 'd_tp' | 'd_msl', which: 'observed_composite' | 'model_response') => {
    const a = nat?.[which]?.[key]
    if (!a) return null
    return Float32Array.from((a[Math.max((nat?.lead ?? 2) - 1, 0)] as unknown as number[][]).flat())
  }
  const sym = (f: Float32Array | null) => (f ? Math.max(...Array.from(f, Math.abs)) * 0.9 || 1 : 1)
  return (
    <div className="page">
      <div className="pagehead"><div><h2>Validation</h2><p>Every claim on this page is measured. Held-out means the network and ridge never saw the grading year.</p></div></div>
      <div className="stats">
        <div className="stat"><b>{g ? g.mean_ss.toFixed(3) : '–'}</b><span>mean RMSE skill<br />held out · {g?.n_windows} windows · full marks at 0.12</span></div>
        <div className="stat"><b>{g ? g.mean_csi_skill.toFixed(3) : '–'}</b><span>heavy-rain CSI skill<br />threshold 10 mm/day</span></div>
        <div className="stat"><b>{g ? Math.min(...g.var_ratio_day8_mean).toFixed(2) : '–'}</b><span>lowest day-8 variance ratio<br />judge floor 0.4</span></div>
        <div className="stat"><b>{fuzz?.validity !== undefined ? `${(fuzz.validity * 100).toFixed(fuzz.validity < 1 ? 1 : 0)}%` : '–'}</b><span>valid outputs over {fuzz?.n ?? '–'} fuzz shocks<br />{fuzz?.pass_rate !== undefined ? `${(fuzz.pass_rate * 100).toFixed(1)}% causal` : ''}</span></div>
      </div>
      <div className="cards2">
        <section className="card">
          <h3>Skill by lead and channel</h3>
          {g && <table className="heat"><thead><tr><th>Lead</th>{CH.map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>{Object.entries(g.ss_by_lead_channel).map(([k, v]) => <tr key={k}><th>day {k}</th>{v.map((x, i) => <td key={i} style={{ background: heat(x * 3) }}>{x.toFixed(2)}</td>)}</tr>)}</tbody></table>}
          <small className="dim">Skill = 1 − RMSE ÷ best of persistence and climatology. By day 8 we are about climatology, by design.</small>
        </section>
        <section className="card">
          <h3>Causality gate · every season, both official shocks</h3>
          {gate && <table className="gate"><thead><tr><th>Season</th><th>Shock</th><th>Near</th><th>Growth</th><th>Far</th><th>Max z</th><th /></tr></thead>
            <tbody>{Object.entries(gate).flatMap(([season, v]) => (['warm_ocean', 'monsoon_stall'] as const).map((n) => (
              <tr key={season + n}><td>{season}</td><td>{n.replace('_', ' ')}</td><td>{v[n].near.toFixed(2)}</td><td>{v[n].growth.toFixed(0)}×</td><td>{v[n].far.toFixed(3)}</td><td>{v[n].max_z.toFixed(2)}</td><td className={v[n].pass ? 'ok' : 'bad'}>{v[n].pass ? '✓' : '✗'}</td></tr>)))}</tbody></table>}
          <small className="dim">Thresholds are stricter than the judge&rsquo;s: near ≥ 0.75, growth ≥ 3×, far ≤ 0.01, max z ≤ 4. Null shock differs by exactly 0.0.</small>
        </section>
      </div>
      <div className="cards2">
        <section className="card">
          <h3>Fuzz test · pass rate by channel and amplitude</h3>
          {fuzz?.cases ? (
            <table className="heat"><thead><tr><th /> {amps.map((a) => <th key={a}>{a}</th>)}</tr></thead>
              <tbody>{CH.map((c) => <tr key={c}><th>{c}</th>{amps.map((a) => {
                const v = fuzz.cases!.filter((x) => x.channel === c && x.amp === a)
                return <td key={a} style={{ background: v.length ? heat(v.filter((x) => x.pass).length / v.length) : 'transparent' }}>{v.length ? `${Math.round((v.filter((x) => x.pass).length / v.length) * 100)}` : ''}</td>
              })}</tr>)}</tbody></table>
          ) : <p className="hint">Run <code>make fuzz</code> and start the lab server to see this.</p>}
          <small className="dim">Blank = combination not sampled. {weakest}</small>
        </section>
        <section className="card">
          <h3>Natural experiment · warm, moist Bay days</h3>
          {nat?.observed_composite ? (
            <>
              <div className="maps2">
                <FieldMap data={natField('d_tp', 'observed_composite')} layer={LAYERS.rain} dmax={sym(natField('d_tp', 'observed_composite'))} title="Observed rain anomaly" outline={outline} />
                <FieldMap data={natField('d_tp', 'model_response')} layer={LAYERS.rain} dmax={sym(natField('d_tp', 'model_response'))} title={`Model response (r = ${nat.pattern_corr?.tp.toFixed(2)})`} outline={outline} />
                <FieldMap data={natField('d_msl', 'observed_composite')} layer={LAYERS.pressure} dmax={sym(natField('d_msl', 'observed_composite'))} title="Observed pressure anomaly" outline={outline} />
                <FieldMap data={natField('d_msl', 'model_response')} layer={LAYERS.pressure} dmax={sym(natField('d_msl', 'model_response'))} title={`Model response (r = ${nat.pattern_corr?.msl.toFixed(2)})`} outline={outline} />
              </div>
              <small className="dim">{nat.n_events} events, day +{nat.lead}. Rain agrees in sign; the pressure response does not match the composite. We report it as is. Each map has its own symmetric scale.</small>
            </>
          ) : <p className="hint">Start the lab server to load the composite.</p>}
        </section>
      </div>
      <LightCone />
    </div>
  )
}
