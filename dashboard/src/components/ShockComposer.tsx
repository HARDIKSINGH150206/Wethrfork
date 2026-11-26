import { useState } from 'react'
import { CHANNELS, UNITS } from '../api/types'
import { chIndex, CELLS } from '../lib/grid'
import { cyclone, dryKerala, gaussian, heatDome, monsoonStall, warmOcean } from '../lib/shocks'
import { useStore } from '../state/store'

export function ShockComposer() {
  const { init, fork } = useStore()
  const [ch, setCh] = useState<(typeof CHANNELS)[number]>('t2m')
  const [amp, setAmp] = useState(3)
  const [lat, setLat] = useState(15)
  const [lon, setLon] = useState(88)
  const [rad, setRad] = useState(4)
  const last = init ? init.subarray(2 * 6 * CELLS, 3 * 6 * CELLS) : null
  const go = (f: () => ReturnType<typeof warmOcean>) => last && fork(f())
  return (
    <section className="panel composer">
      <h3>Shock composer</h3>
      <div className="presets">
        <button disabled={!last} onClick={() => go(() => warmOcean(last!))}>Warm Bay +3 K</button>
        <button disabled={!last} onClick={() => go(() => monsoonStall(last!))}>Monsoon stall</button>
        <button disabled={!last} onClick={() => go(() => cyclone(lat, lon))}>Plant a cyclone</button>
        <button disabled={!last} onClick={() => go(() => heatDome())}>Heat dome</button>
        <button disabled={!last} onClick={() => go(() => dryKerala(last!))}>Dry Kerala</button>
      </div>
      <h4>Custom Gaussian</h4>
      <label>channel
        <select value={ch} onChange={(e) => setCh(e.target.value as typeof ch)}>
          {CHANNELS.map((c) => <option key={c}>{c}</option>)}
        </select>
      </label>
      <label>amplitude ({UNITS[ch]})<input type="number" value={amp} step="any" onChange={(e) => setAmp(+e.target.value)} /></label>
      <label>lat<input type="number" value={lat} onChange={(e) => setLat(+e.target.value)} /></label>
      <label>lon<input type="number" value={lon} onChange={(e) => setLon(+e.target.value)} /></label>
      <label>radius (cells)<input type="number" value={rad} min={1} max={8} onChange={(e) => setRad(+e.target.value)} /></label>
      <button className="primary" disabled={!last} onClick={() => fork(gaussian(chIndex(ch), amp, lat, lon, rad, false, `${ch} ${amp > 0 ? '+' : ''}${amp} ${UNITS[ch]}`))}>
        Fork universe
      </button>
    </section>
  )
}
