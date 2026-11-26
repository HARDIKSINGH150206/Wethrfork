import { useEffect } from 'react'
import { IconPause, IconPlay } from '../icons'
import { CONTROL, useStore } from '../../state/store'

export function Timeline() {
  const { tf, playing, speed, set, universes, selected } = useStore()
  useEffect(() => {
    if (!playing) return
    let raf = 0, last = performance.now(), acc = 0
    const tick = (now: number) => {
      const dt = (now - last) / 1000
      last = now; acc += dt
      if (acc > 1 / 30) { // update the store at about 30 fps
        const st = useStore.getState()
        const next = st.tf + acc * st.speed * 0.7
        useStore.setState({ tf: next > 9 ? 0 : next })
        acc = 0
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing])
  const day = Math.round(tf)
  const u = universes[selected], c = universes[CONTROL]
  return (
    <footer className="timeline" data-ui>
      <button className="play" onClick={() => set({ playing: !playing })} aria-label={playing ? 'Pause' : 'Play'}>{playing ? <IconPause /> : <IconPlay />}</button>
      <button className="speed" onClick={() => set({ speed: speed >= 2 ? 0.5 : speed * 2 })} title="Playback speed">{speed}×</button>
      <div className="track">
        <div className="fill" style={{ width: `${(tf / 9) * 100}%` }} />
        <input type="range" min={0} max={9} step={0.01} value={tf} onChange={(e) => set({ tf: +e.target.value, playing: false })} aria-label="Forecast day" />
        <div className="ticks">{Array.from({ length: 10 }, (_, d) => (
          <button key={d} className={d === day ? 'on' : ''} onClick={() => set({ tf: d, playing: false })}>+{d + 1}</button>
        ))}</div>
      </div>
      <div className="runinfo">
        <span>Day +{(tf + 1).toFixed(1)}</span>
        <small>{c?.wallMs ? `control ${Math.round(c.wallMs)} ms` : ''}{u && u !== c && u.wallMs ? ` · universe ${Math.round(u.wallMs)} ms` : ''}</small>
      </div>
    </footer>
  )
}
