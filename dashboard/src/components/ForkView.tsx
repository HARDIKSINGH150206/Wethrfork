import { useEffect, useMemo, useState } from 'react'
import { CONTROL, useStore } from '../state/store'
import { robustMax, scaleFor } from '../lib/colors'
import { chIndex, diff, field } from '../lib/grid'
import { hardReach, judgeRadius, withinRadius } from '../lib/ring'
import { MapCanvas } from './MapCanvas'

export function ForkView() {
  const { universes, selected, day, channel, setDay } = useStore()
  const [outline, setOutline] = useState<number[][] | null>(null)
  const [play, setPlay] = useState(false)
  useEffect(() => {
    fetch('/india_outline.geojson').then((r) => r.json()).then((g) => setOutline(g.features[0].geometry.coordinates[0])).catch(() => null)
  }, [])
  useEffect(() => {
    if (!play) return
    const t = setInterval(() => setDay((useStore.getState().day + 1) % 10), 900)
    return () => clearInterval(t)
  }, [play, setDay])

  const ctl = universes[CONTROL]
  const uni = universes[selected]
  const c = chIndex(channel)
  const a = ctl?.rollout ? field(ctl.rollout, day, c) : null
  const b = uni?.rollout ? field(uni.rollout, day, c) : null
  const d = a && b ? diff(b, a) : null
  const dmax = useMemo(() => (d ? robustMax(d) : 1), [d])
  const base = scaleFor(channel)
  const dscale = scaleFor(channel, true, dmax)
  const ring = useMemo(() => (uni?.box ? withinRadius(uni.box, judgeRadius(day + 1)) : null), [uni?.box, day])
  const hard = useMemo(() => (uni?.box ? withinRadius(uni.box, hardReach(day + 1)) : null), [uni?.box, day])

  return (
    <section className="panel fork">
      <div className="maps">
        <MapCanvas data={a} scale={base} title="Control" outline={outline} />
        <MapCanvas data={b} scale={base} title={uni ? `Universe: ${uni.name}` : 'Universe'} outline={outline} box={uni?.box} />
        <MapCanvas data={d} scale={dscale} title={`Delta (${dscale.unit})`} outline={outline} box={uni?.box} ring={ring} hard={hard} />
      </div>
      <div className="scrub">
        <button onClick={() => setPlay(!play)}>{play ? '⏸' : '▶'}</button>
        <input type="range" min={0} max={9} value={day} onChange={(e) => setDay(+e.target.value)} />
        <span>day +{day + 1}</span>
        <span className="legend">
          <i style={{ borderColor: '#ffd24d' }} /> judge radius 3+8·day <i style={{ borderColor: '#ff7b54' }} /> our hard reach 8·day
        </span>
      </div>
      {uni?.status === 'loading' && <p className="note">running the model…</p>}
      {uni?.status === 'error' && <p className="note err">{uni.error}</p>}
    </section>
  )
}
