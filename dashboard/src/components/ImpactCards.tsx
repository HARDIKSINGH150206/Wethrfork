import { CONTROL, useStore } from '../state/store'
import { chIndex, CELLS, NLON, latOf, lonOf, NLAT } from '../lib/grid'
import { REGIONS } from '../lib/regions'

function regionMean(roll: Float32Array, day: number, c: number, box: [number, number, number, number], land: number[][] | null): number {
  let s = 0, n = 0
  const off = (day * 6 + c) * CELLS
  for (let i = 0; i < NLAT; i++)
    for (let j = 0; j < NLON; j++) {
      if (latOf(i) < box[0] || latOf(i) > box[1] || lonOf(j) < box[2] || lonOf(j) > box[3]) continue
      if (land && land[i][j] < 0.5) continue
      s += roll[off + i * NLON + j]
      n++
    }
  return n ? s / n : NaN
}

export function ImpactCards() {
  const { universes, selected, day, meta } = useStore()
  const ctl = universes[CONTROL]?.rollout
  const uni = universes[selected]?.rollout
  if (!ctl || !uni || selected === CONTROL) return <section className="panel impact"><h3>Impact</h3><p className="note">Fork a universe to compare regions.</p></section>
  const land = meta?.land_sea_mask ?? null
  const rows = REGIONS.map((r) => {
    const dT = regionMean(uni, day, chIndex('t2m'), r.box, land) - regionMean(ctl, day, chIndex('t2m'), r.box, land)
    const rainC = regionMean(ctl, day, chIndex('tp'), r.box, land)
    const rainU = regionMean(uni, day, chIndex('tp'), r.box, land)
    return { ...r, dT, rainC, rainU, dRain: rainU - rainC }
  }).sort((a, b) => Math.abs(b.dRain) + Math.abs(b.dT) - Math.abs(a.dRain) - Math.abs(a.dT))
  return (
    <section className="panel impact">
      <h3>Regional impact (land cells, day +{day + 1})</h3>
      <div className="cards">
        {rows.slice(0, 8).map((r) => (
          <div key={r.id} className="card">
            <b>{r.name}</b>
            <span>ΔT {r.dT >= 0 ? '+' : ''}{r.dT.toFixed(2)} K</span>
            <span>rain {r.rainC.toFixed(1)} → {r.rainU.toFixed(1)} mm/day</span>
          </div>
        ))}
      </div>
      <p className="note">1° cells (~110 km). Differences are the model's own response to the shock.</p>
    </section>
  )
}
