import { useMemo } from 'react'
import { LAYERS } from '../../lib/layers'
import { sample } from '../../lib/interp'
import { scalarAt } from '../../lib/layers'
import { pointSeries } from '../../lib/series'
import { CONTROL, useStore } from '../../state/store'
import type { Pin } from '../../state/store'

interface Props { pin: Pin; x: number; y: number; bounds: { w: number; h: number } }
const W = 270, H = 96

export function PointPopup({ pin, x, y, bounds }: Props) {
  const { universes, order, selected, layer, units, tf, set, runSensitivity, sensBusy, sens, labOnline } = useStore()
  const def = LAYERS[layer]
  const series = useMemo(
    () => order.map((id) => ({ id, name: universes[id].name, v: universes[id].rollout ? pointSeries(universes[id].rollout!, layer, pin.lat, pin.lon) : null })),
    [order, universes, layer, pin],
  )
  const all = series.flatMap((s) => s.v ?? [])
  if (!all.length) return null
  const lo = Math.min(...all), hi = Math.max(...all), pad = (hi - lo || 1) * 0.15
  const sx = (d: number) => 8 + (d / 9) * (W - 16)
  const sy = (v: number) => H - 14 - ((v - (lo - pad)) / (hi - lo + 2 * pad)) * (H - 24)
  const cur = universes[selected]?.rollout ? sample(scalarAt(universes[selected].rollout!, tf, layer), pin.lat, pin.lon) : NaN
  const left = Math.min(Math.max(x + 16, 8), bounds.w - W - 24), top = Math.min(Math.max(y - 20, 70), bounds.h - 250)
  return (
    <div className="popup" data-ui style={{ left, top, width: W }} onPointerDown={(e) => e.stopPropagation()}>
      <div className="phead">
        <div><b>{pin.lat.toFixed(1)}°N {pin.lon.toFixed(1)}°E</b><small>{def.label} · day +{Math.round(tf) + 1}</small></div>
        <button onClick={() => set({ pin: null, sens: null })} aria-label="Close">×</button>
      </div>
      <div className="pval">{def.fmt(cur, units)}</div>
      <svg width={W} height={H} className="spark">
        {[0, 3, 6, 9].map((d) => <g key={d}><line x1={sx(d)} x2={sx(d)} y1={6} y2={H - 14} stroke="rgba(255,255,255,0.08)" /><text x={sx(d)} y={H - 2} textAnchor="middle">+{d + 1}</text></g>)}
        {series.map((s) => s.v && (
          <polyline key={s.id} fill="none" strokeWidth={s.id === selected ? 2.4 : 1.2} stroke={s.id === CONTROL ? '#9fb3c8' : s.id === selected ? '#4cc2ff' : '#c58bff'}
            points={s.v.map((v, d) => `${sx(d)},${sy(v)}`).join(' ')} />
        ))}
        <line x1={sx(Math.min(tf, 9))} x2={sx(Math.min(tf, 9))} y1={4} y2={H - 14} stroke="#ffd24d" strokeWidth={1.4} />
      </svg>
      <div className="plegend">{series.map((s) => <span key={s.id}><i style={{ background: s.id === CONTROL ? '#9fb3c8' : s.id === selected ? '#4cc2ff' : '#c58bff' }} />{s.name}</span>)}</div>
      <button className="sensbtn" disabled={!labOnline || sensBusy} onClick={() => runSensitivity(pin.lat, pin.lon)}>
        {sensBusy ? 'tracing…' : sens ? 'Where does this come from? ✓' : 'Where does this come from?'}
      </button>
      {sens && <small className="dim">Network sensitivity of {sens.channel} at day +{sens.lead} to today&rsquo;s fields. Dominant source channel: <b>{sens.top}</b>.</small>}
    </div>
  )
}
