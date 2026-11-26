import { useMemo } from 'react'
import { LAYERS, divergingLut, lut } from '../../lib/layers'
import { deltaScale } from '../../lib/series'
import { NEXT_PRESS, NEXT_TEMP, NEXT_WIND } from '../../lib/units'
import { CONTROL, useStore } from '../../state/store'

/** Bottom-right: the "model" picker (control and every forked universe) above a compact colour legend. */
export function Legend() {
  const { layer, units, delta, universes, selected, setUnits, order, select } = useStore()
  const def = LAYERS[layer]
  const ctl = universes[CONTROL]?.rollout, uni = universes[selected]?.rollout
  const isDelta = delta && selected !== CONTROL && !!ctl && !!uni
  const dmax = useMemo(() => (isDelta ? deltaScale(uni!, ctl!, layer, def.deltaFloor) : 1), [isDelta, uni, ctl, layer, def.deltaFloor])
  const gradient = useMemo(() => {
    const table = isDelta ? divergingLut() : lut(def)
    const stops: string[] = []
    for (let k = 0; k < 512; k += 12) stops.push(`rgb(${table[k * 4]},${table[k * 4 + 1]},${table[k * 4 + 2]}) ${(k / 511) * 100}%`)
    return `linear-gradient(90deg, ${stops.join(',')})`
  }, [def, isDelta])
  const cycle = () => {
    if (layer === 'temp') setUnits({ temp: NEXT_TEMP[units.temp] })
    else if (layer === 'wind') setUnits({ wind: NEXT_WIND[units.wind] })
    else if (layer === 'pressure') setUnits({ press: NEXT_PRESS[units.press] })
  }
  const pos = (v: number) => {
    const t = Math.min(Math.max((v - def.lo) / (def.hi - def.lo), 0), 1)
    return (def.warp === 'sqrt' ? Math.sqrt(t) : t) * 100
  }
  return (
    <div className="br" data-ui>
      <div className="models">
        {order.map((id) => (
          <button key={id} className={id === selected ? 'on' : ''} onClick={() => select(id)} title={universes[id].name}>
            {id === CONTROL ? 'Control' : universes[id].name}
            {universes[id].status === 'loading' && <i className="spin" />}
          </button>
        ))}
      </div>
      <div className="leg" onClick={cycle} title="Click to change units">
        <span className="u">{isDelta ? `Δ${def.unit(units)}` : def.unit(units)}</span>
        <div className="grad" style={{ background: gradient }}>
          {isDelta
            ? [-1, -0.5, 0, 0.5, 1].map((f) => <span key={f} style={{ left: `${50 + f * 50}%` }}>{f === 0 ? '0' : def.fmt(f * dmax, units, true).split(' ')[0]}</span>)
            : def.ticks.map((v) => <span key={v} style={{ left: `${pos(v)}%` }}>{Math.round(def.disp(v, units))}</span>)}
        </div>
      </div>
    </div>
  )
}
