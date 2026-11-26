import { useMemo } from 'react'
import { LAYERS, divergingLut, lut } from '../../lib/layers'
import { deltaScale } from '../../lib/series'
import { NEXT_PRESS, NEXT_TEMP, NEXT_WIND } from '../../lib/units'
import { CONTROL, useStore } from '../../state/store'

export function Legend() {
  const { layer, units, delta, universes, selected, setUnits } = useStore()
  const def = LAYERS[layer]
  const ctl = universes[CONTROL]?.rollout, uni = universes[selected]?.rollout
  const isDelta = delta && selected !== CONTROL && ctl && uni
  const dmax = useMemo(() => (isDelta ? deltaScale(uni!, ctl!, layer, def.deltaFloor) : 1), [isDelta, uni, ctl, layer, def.deltaFloor])
  const gradient = useMemo(() => {
    const table = isDelta ? divergingLut() : lut(def)
    const stops: string[] = []
    for (let k = 0; k < 512; k += 16) stops.push(`rgba(${table[k * 4]},${table[k * 4 + 1]},${table[k * 4 + 2]},${Math.max(table[k * 4 + 3] / 255, 0.35)}) ${(k / 511) * 100}%`)
    return `linear-gradient(90deg, ${stops.join(',')})`
  }, [def, isDelta])
  const cycle = () => {
    if (layer === 'temp') setUnits({ temp: NEXT_TEMP[units.temp] })
    else if (layer === 'wind') setUnits({ wind: NEXT_WIND[units.wind] })
    else if (layer === 'pressure') setUnits({ press: NEXT_PRESS[units.press] })
  }
  const pos = (v: number) => {
    const t = (v - def.lo) / (def.hi - def.lo)
    return (def.warp === 'sqrt' ? Math.sqrt(Math.min(Math.max(t, 0), 1)) : Math.min(Math.max(t, 0), 1)) * 100
  }
  return (
    <div className="legend" data-ui>
      <button className="unit" onClick={cycle} title="Click to change units">{isDelta ? `Δ ${def.unit(units)}` : def.unit(units)}</button>
      <div className="bar" style={{ background: gradient }}>
        {isDelta
          ? [-1, -0.5, 0, 0.5, 1].map((f) => <span key={f} style={{ left: `${50 + f * 50}%` }}>{f === 0 ? '0' : def.fmt(f * dmax, units, true).split(' ')[0]}</span>)
          : def.ticks.map((v) => <span key={v} style={{ left: `${pos(v)}%` }}>{Number(def.disp(v, units).toFixed(def.id === 'pressure' ? 0 : 1))}</span>)}
      </div>
    </div>
  )
}
