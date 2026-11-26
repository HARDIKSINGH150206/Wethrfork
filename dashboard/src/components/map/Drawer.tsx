import { useState } from 'react'
import { CHANNELS, UNITS } from '../../api/types'
import { CELLS, chIndex } from '../../lib/grid'
import { dayName } from '../../lib/dates'
import { rainfallExposure, windowStart } from '../../lib/exposure'
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

function AuditPanel() {
  const { universes, selected, labOnline, tf, meta, doy, weekday } = useStore()
  const [thr, setThr] = useState(50)
  const u = universes[selected], ctl = universes[CONTROL]?.rollout
  if (selected === CONTROL || !u?.rollout || !ctl) return <p className="hint">Fork a universe to audit it: the official causality checks run live on every shock.</p>
  const v = u.verdict
  const scn = u.rollout
  const N_DAYS = 3
  const start = windowStart(tf, N_DAYS)
  const land = meta?.land_sea_mask ?? null
  const rows = land ? [
    { name: 'All land in the domain', ...rainfallExposure(ctl, scn, start, N_DAYS, thr, land, null) },
    ...REGIONS.map((r) => ({ name: r.name, ...rainfallExposure(ctl, scn, start, N_DAYS, thr, land, r.box) })),
  ] : []
  const [total, ...regions] = rows
  regions.sort((a, b) => Math.abs(b.scnFrac - b.ctlFrac) + Math.abs(b.scnMm - b.ctlMm) / 200 - (Math.abs(a.scnFrac - a.ctlFrac) + Math.abs(a.scnMm - a.ctlMm) / 200))
  const pct = (x: number) => `${Math.round(x * 100)}%`
  const dpp = (a: number, b: number) => { const d = Math.round((b - a) * 100); return `${d >= 0 ? '+' : ''}${d} pp` }
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
      <h4>Rainfall exposure</h4>
      <div className="expo-head">
        <span>3-day accumulation, <b>{dayName(doy, start + 1, weekday, true)} to {dayName(doy, start + N_DAYS, weekday, true)}</b></span>
        <div className="thr" title="Declared threshold: accumulated rainfall over the 3 days">
          {[25, 50, 100].map((x) => <button key={x} className={thr === x ? 'on' : ''} onClick={() => setThr(x)}>{x} mm</button>)}
        </div>
      </div>
      <table className="impact expo">
        <thead><tr><th>Region</th><th>3-day rain</th><th>Land above {thr} mm</th></tr></thead>
        <tbody>
          {total && <tr className="total"><td>{total.name}</td><td>{total.ctlMm.toFixed(0)}→<b>{total.scnMm.toFixed(0)}</b> <small>mm</small></td><td>{pct(total.ctlFrac)}→<b>{pct(total.scnFrac)}</b> <small className={total.scnFrac >= total.ctlFrac ? 'up' : 'down'}>{dpp(total.ctlFrac, total.scnFrac)}</small></td></tr>}
          {regions.slice(0, 7).map((r) => (
            <tr key={r.name}><td>{r.name}</td><td>{r.ctlMm.toFixed(0)}→<b>{r.scnMm.toFixed(0)}</b> <small>mm</small></td><td>{pct(r.ctlFrac)}→<b>{pct(r.scnFrac)}</b> <small className={r.scnFrac >= r.ctlFrac ? 'up' : 'down'}>{dpp(r.ctlFrac, r.scnFrac)}</small></td></tr>
          ))}
        </tbody>
      </table>
      <p className="hint">Rainfall exposure only: accumulated model rainfall and the share of land <i>area</i> (latitude-weighted 1° land cells) above the threshold you choose, control against this scenario. It is not a flood probability or a crop-loss estimate. The scenario is the model&rsquo;s own response, not a verified forecast.</p>
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
