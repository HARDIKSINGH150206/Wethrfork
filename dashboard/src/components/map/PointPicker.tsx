import { useMemo } from 'react'
import { CELLS } from '../../lib/grid'
import { sample } from '../../lib/interp'
import { LAYERS, scalarAt, windAt } from '../../lib/layers'
import { placeName } from '../../lib/dates'
import { CONTROL, useStore } from '../../state/store'
import type { Pin } from '../../state/store'

const U = new Float32Array(CELLS), V = new Float32Array(CELLS)

/** Windy-style picker: a small bubble above the clicked point with the value of the active layer. */
export function PointPicker({ pin, x, y }: { pin: Pin; x: number; y: number }) {
  const { universes, selected, layer, units, tf, set, meteo, runSensitivity, sensBusy, labOnline, sens } = useStore()
  const roll = universes[selected]?.rollout ?? null
  const ctl = universes[CONTROL]?.rollout ?? null
  const info = useMemo(() => {
    if (!roll) return null
    const v = sample(scalarAt(roll, tf, layer), pin.lat, pin.lon)
    const c = ctl && selected !== CONTROL ? sample(scalarAt(ctl, tf, layer), pin.lat, pin.lon) : null
    windAt(roll, tf, U, V)
    const u = sample(U, pin.lat, pin.lon), w = sample(V, pin.lat, pin.lon)
    const dirFrom = (Math.atan2(-u, -w) * 180) / Math.PI // meteorological: where the wind comes from
    return { v, c, dir: (dirFrom + 360) % 360 }
  }, [roll, ctl, tf, layer, pin, selected])
  if (!info) return null
  const def = LAYERS[layer]
  return (
    <div className="picker" data-ui style={{ left: x, top: y }} onPointerDown={(e) => e.stopPropagation()}>
      <div className="bubble">
        <div className="pv">
          {layer === 'wind' && <span className="arrow" style={{ transform: `rotate(${info.dir + 180}deg)` }}>↑</span>}
          <b>{def.fmt(info.v, units)}</b>
          {info.c !== null && <small className={info.v - info.c >= 0 ? 'up' : 'down'}>{info.v - info.c >= 0 ? '+' : ''}{def.fmt(info.v - info.c, units, true)}</small>}
          <button className="x" onClick={() => set({ pin: null, sens: null, meteo: false })} aria-label="Close">×</button>
        </div>
        <div className="pa">
          <span>{placeName(pin.lat, pin.lon)}</span>
          <button onClick={() => set({ meteo: !meteo })}>{meteo ? 'Hide forecast' : 'Forecast'}</button>
          <button disabled={!labOnline || sensBusy} onClick={() => runSensitivity(pin.lat, pin.lon)}>{sensBusy ? '…' : sens ? 'Origin ✓' : 'Origin'}</button>
        </div>
      </div>
      <i className="stem" />
    </div>
  )
}
