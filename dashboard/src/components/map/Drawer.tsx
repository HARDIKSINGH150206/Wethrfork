import { useState } from 'react'
import { CHANNELS, UNITS } from '../../api/types'
import { CELLS, NLAT, NLON, chIndex, latOf, lonOf } from '../../lib/grid'
import { REGIONS } from '../../lib/regions'
import { boxShock, cyclone, dryKerala, heatDome, monsoonStall, warmOcean } from '../../lib/shocks'
import { IconBolt, IconShield } from '../icons'
import { CONTROL, useStore } from '../../state/store'

function ShockPanel() {
  const { init, fork, pin, drawnBox, set, drawMode, universes, order, selected, select } = useStore()
  const [ch, setCh] = useState<(typeof CHANNELS)[number]>('t2m')
  const [amt, setAmt] = useState(3)
  const [rel, setRel] = useState(false)
  const last = init ? init.subarray(2 * 6 * CELLS, 3 * 6 * CELLS) : null
  const go = (f: (l: Float32Array) => ReturnType<typeof warmOcean>) => last && void fork(f(last))
  return (
    <>
      <h4>Presets</h4>
      <div className="presets">
        <button disabled={!last} onClick={() => go((l) => warmOcean(l))}><b>Warm Bay</b><small>+3 K, +15% moisture</small></button>
        <button disabled={!last} onClick={() => go((l) => monsoonStall(l))}><b>Monsoon stall</b><small>−40% wind, Arabian Sea</small></button>
        <button disabled={!last} onClick={() => go(() => cyclone(pin?.lat ?? 15, pin?.lon ?? 88))}><b>Plant a cyclone</b><small>{pin ? 'at the pinned point' : 'at 15°N 88°E'}</small></button>
        <button disabled={!last} onClick={() => go(() => heatDome())}><b>Heat dome</b><small>+5 K, Rajasthan</small></button>
        <button disabled={!last} onClick={() => go((l) => dryKerala(l))}><b>Dry Kerala</b><small>−30% moisture</small></button>
      </div>
      <h4>Your own shock</h4>
      <button className={`draw ${drawMode ? 'on' : ''}`} onClick={() => set({ drawMode: !drawMode })}>{drawMode ? 'Drag a rectangle on the map…' : drawnBox ? 'Redraw the box' : 'Draw a box on the map'}</button>
      {drawnBox && <p className="boxinfo">{drawnBox[0].toFixed(1)}–{drawnBox[1].toFixed(1)}°N · {drawnBox[2].toFixed(1)}–{drawnBox[3].toFixed(1)}°E</p>}
      <div className="form">
        <label>Channel<select value={ch} onChange={(e) => setCh(e.target.value as typeof ch)}>{CHANNELS.map((c) => <option key={c}>{c}</option>)}</select></label>
        <label>Mode<select value={rel ? 'rel' : 'abs'} onChange={(e) => setRel(e.target.value === 'rel')}><option value="abs">add ({UNITS[ch]})</option><option value="rel">% of current</option></select></label>
        <label>Amount<input type="number" step="any" value={amt} onChange={(e) => setAmt(+e.target.value)} /></label>
      </div>
      <button className="primary" disabled={!last || !drawnBox} onClick={() => last && drawnBox && void fork(boxShock(chIndex(ch), rel ? amt / 100 : amt, rel, drawnBox, last, `${ch} ${amt > 0 ? '+' : ''}${amt}${rel ? '%' : ' ' + UNITS[ch]}`))}>
        Fork universe
      </button>
      <h4>Universes</h4>
      <ul className="unis">
        {order.map((id) => {
          const u = universes[id]
          const v = u.verdict
          return (
            <li key={id} className={id === selected ? 'sel' : ''} onClick={() => select(id)}>
              <b>{u.name}</b>
              <small>{u.status === 'ready' ? `${Math.round(u.wallMs ?? 0)} ms` : u.status}</small>
              {v && <span className="mini">{(['nonzero', 'localized', 'propagates', 'stable'] as const).map((k) => <i key={k} className={v.checks[k] ? 'ok' : 'bad'} title={k} />)}</span>}
            </li>
          )
        })}
      </ul>
      {order.length === 1 && <p className="hint">Fork a universe, then use <b>Delta</b> or <b>Compare</b> on the right.</p>}
      {universes[CONTROL]?.status === 'error' && <p className="hint err">{universes[CONTROL].error}</p>}
    </>
  )
}

function regionMean(roll: Float32Array, d: number, c: number, box: [number, number, number, number], land: number[][] | null): number {
  let s = 0, n = 0
  const off = (d * 6 + c) * CELLS
  for (let i = 0; i < NLAT; i++) for (let j = 0; j < NLON; j++) {
    if (latOf(i) < box[0] || latOf(i) > box[1] || lonOf(j) < box[2] || lonOf(j) > box[3]) continue
    if (land && land[i][j] < 0.5) continue
    s += roll[off + i * NLON + j]; n++
  }
  return n ? s / n : NaN
}

function AuditPanel() {
  const { universes, selected, labOnline, tf, meta } = useStore()
  const u = universes[selected], ctl = universes[CONTROL]?.rollout
  if (selected === CONTROL || !u?.rollout || !ctl) return <p className="hint">Fork a universe to audit it: the official causality checks run live on every shock.</p>
  const v = u.verdict
  const d = Math.min(Math.round(tf), 9)
  const rows = REGIONS.map((r) => ({
    name: r.name,
    dT: regionMean(u.rollout!, d, 0, r.box, meta?.land_sea_mask ?? null) - regionMean(ctl, d, 0, r.box, meta?.land_sea_mask ?? null),
    c: regionMean(ctl, d, 1, r.box, meta?.land_sea_mask ?? null),
    s: regionMean(u.rollout!, d, 1, r.box, meta?.land_sea_mask ?? null),
  })).sort((a, b) => Math.abs(b.s - b.c) - Math.abs(a.s - a.c)).slice(0, 6)
  const ood = v?.ood
  return (
    <>
      <h4>Limits verdict</h4>
      {!labOnline ? <p className="hint">Lab offline: the checks run in CI.</p> : !v ? <p className="hint">computing…</p> : (
        <>
          <ul className="checks">
            <li className={v.checks.nonzero ? 'ok' : 'bad'}>{v.checks.nonzero ? '✓' : '✗'} non-zero response</li>
            <li className={v.checks.localized ? 'ok' : 'bad'}>{v.checks.localized ? '✓' : '✗'} localized <small>near {v.near_frac_day1.toFixed(2)}</small></li>
            <li className={v.checks.propagates ? 'ok' : 'bad'}>{v.checks.propagates ? '✓' : '✗'} propagates <small>×{v.growth_ratio.toFixed(1)}, far {v.far_frac_max.toFixed(3)}</small></li>
            <li className={v.checks.stable ? 'ok' : 'bad'}>{v.checks.stable ? '✓' : '✗'} stable <small>max z {v.max_z.toFixed(2)}</small></li>
          </ul>
          {ood && (
            <div className="ood"><span>Out-of-distribution</span>
              <div className="meter"><i style={{ width: `${Math.min(ood.max_abs_z_vs_clim_std / 12, 1) * 100}%` }} className={ood.level} /></div>
              <small><b className={`ood-${ood.level}`}>{ood.level}</b> · {ood.max_abs_z_vs_clim_std.toFixed(1)}σ of local variability</small></div>
          )}
        </>
      )}
      <h4>Regional impact · day +{d + 1}</h4>
      <table className="impact"><tbody>
        {rows.map((r) => <tr key={r.name}><td>{r.name}</td><td>{r.c.toFixed(1)}→<b>{r.s.toFixed(1)}</b> <small>mm/d</small></td><td>{r.dT >= 0 ? '+' : ''}{r.dT.toFixed(2)} <small>K</small></td></tr>)}
      </tbody></table>
      <p className="hint">Mean over land cells of 1° (~110 km). The model&rsquo;s own response, not a verified forecast.</p>
    </>
  )
}

export function Drawer() {
  const { drawer, set } = useStore()
  return (
    <div className={`drawer ${drawer ? 'open' : ''}`} data-ui>
      {drawer && (
        <div className="panel">
          <div className="ptabs">
            <button className={drawer === 'shock' ? 'on' : ''} onClick={() => set({ drawer: 'shock' })}><IconBolt /> Shocks</button>
            <button className={drawer === 'audit' ? 'on' : ''} onClick={() => set({ drawer: 'audit' })}><IconShield /> Audit</button>
            <button className="x" onClick={() => set({ drawer: null })} aria-label="Close">×</button>
          </div>
          {drawer === 'shock' ? <ShockPanel /> : <AuditPanel />}
        </div>
      )}
    </div>
  )
}
