import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { LAYERS, divergingLut, lut } from '../../lib/layers'
import { deltaScale } from '../../lib/series'
import { NEXT_PRESS, NEXT_TEMP, NEXT_WIND } from '../../lib/units'
import { CONTROL, useStore } from '../../state/store'
import { useMap } from '../../state/mapctl'

/** Bottom-left colour legend: a slim capsule with the unit on the left and the values printed inside the colours. */
export function Legend() {
  const { layer, units, delta, universes, selected, setUnits } = useStore()
  const def = LAYERS[layer]
  const ctl = universes[CONTROL]?.rollout, uni = universes[selected]?.rollout
  const isDelta = delta && selected !== CONTROL && !!ctl && !!uni
  const dmax = useMemo(() => (isDelta ? deltaScale(uni!, ctl!, layer, def.deltaFloor) : 1), [isDelta, uni, ctl, layer, def.deltaFloor])
  const gradient = useMemo(() => {
    const table = isDelta ? divergingLut() : lut(def)
    const stops: string[] = []
    for (let k = 0; k < 512; k += 12) {
      const a = Math.max(table[k * 4 + 3] / 255, 0.55) // keep faint colours (light rain, small deltas) visible in the key
      stops.push(`rgba(${table[k * 4]},${table[k * 4 + 1]},${table[k * 4 + 2]},${a}) ${(k / 511) * 100}%`)
    }
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
  // Labels are thinned to the width the bar actually has, so they never run into each other (phones, crowded scales).
  const grad = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(300)
  useLayoutEffect(() => {
    const el = grad.current
    if (!el) return
    const ro = new ResizeObserver(() => setWidth(el.clientWidth || 300))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  const raw: [number, string][] = isDelta
    ? [-1, -0.5, 0, 0.5, 1].map((f) => [50 + f * 50, f === 0 ? '0' : def.fmt(f * dmax, units, true).split(' ')[0]])
    : def.ticks.map((v) => [pos(v), String(Math.round(def.disp(v, units)))])
  const labels: [number, string][] = []
  for (const [p, txt] of raw) {
    const need = ((txt.length * 6.5 + 8) / width) * 100 // label width plus a gap, in percent of the bar
    if (!labels.length || p - labels[labels.length - 1][0] >= need) labels.push([p, txt])
  }
  const align = (p: number) => (p < 4 ? 'translate(2px, -50%)' : p > 96 ? 'translate(calc(-100% - 3px), -50%)' : 'translate(-50%, -50%)')
  return (
    <div className="legend" data-ui onClick={cycle} title="Click to change units">
      <span className="u">{isDelta ? `Δ ${def.unit(units)}` : def.unit(units)}</span>
      <div className="grad" ref={grad} style={{ background: gradient }}>
        {labels.map(([p, txt]) => <span key={`${p}|${txt}`} style={{ left: `${p}%`, transform: align(p) }}>{txt}</span>)}
      </div>
    </div>
  )
}

/** Bottom-right run picker, like a forecast-model switch: the control run and every forked universe. */
export function ModelPicker() {
  const { universes, order, selected, select } = useStore()
  if (!order.length) return null
  return (
    <div className="models" data-ui role="tablist" aria-label="Runs">
      {order.map((id) => {
        const u = universes[id]
        return (
          <button key={id} role="tab" aria-selected={id === selected} className={id === selected ? 'on' : ''} onClick={() => select(id)} title={u.name}>
            <b>{id === CONTROL ? 'Control' : u.name}</b>
            {u.status === 'loading' ? <i className="spin" /> : u.status === 'ready' && u.wallMs ? <small>{Math.round(u.wallMs)} ms</small> : null}
          </button>
        )
      })}
    </div>
  )
}

const dms = (v: number, pos: string, neg: string) => {
  const a = Math.abs(v), d = Math.floor(a), m = Math.floor((a - d) * 60)
  return `${d}° ${String(m).padStart(2, '0')}′ ${v >= 0 ? pos : neg}`
}

/** Bottom-left cursor position. */
export function Coords() {
  const hover = useMap((m) => m.hover)
  const cy = useMap((m) => m.view.cy), cx = useMap((m) => m.view.cx)
  const p = hover ?? { lat: cy, lon: cx }
  return <div className="coords">{dms(p.lat, 'N', 'S')}, {dms(p.lon, 'E', 'W')}</div>
}

const NICE = [25, 50, 100, 200, 250, 500, 1000, 2000]
/** Bottom-right scale bar, measured along the parallel at the centre of the view. */
export function ScaleBar() {
  const view = useMap((m) => m.view)
  const kmPerPx = (111.32 * Math.cos((view.cy * Math.PI) / 180)) / view.scale
  const km = [...NICE].reverse().find((k) => k / kmPerPx <= 90) ?? NICE[0]
  return <div className="scale"><span>{km} km</span><i style={{ width: km / kmPerPx }} /></div>
}

/** Bottom-centre sources line. */
export function Attribution() {
  const meta = useStore((s) => s.meta)
  const ver = meta?.model_name.replace('wethrfork-', '').replace('-speedlimit', '') ?? ''
  return <div className="attrib">© Wethrfork {ver}, ERA5 (C3S) via WeatherBench 2, NASA Blue Marble, Natural Earth</div>
}
