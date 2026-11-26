import { useEffect, useRef, useState } from 'react'
import { IconPause, IconPlay, IconSkipBack } from '../icons'
import { dayLabel, dayName } from '../../lib/dates'
import { useStore } from '../../state/store'

const LAST = 9 // tf runs 0 (day +1) to 9 (day +10)
const TICKS = Array.from({ length: LAST * 4 + 1 }, (_, k) => k / 4) // one tick every 6 hours

/** Bottom-centre timeline capsule: play, the current forecast time, 6-hourly ticks with a blue marker, hover time. */
export function Timeline() {
  const { tf, playing, speed, set, doy, weekday } = useStore()
  const bar = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<number | null>(null)
  useEffect(() => {
    if (!playing) return
    let raf = 0, last = performance.now(), acc = 0
    const tick = (now: number) => {
      acc += (now - last) / 1000; last = now
      if (acc > 1 / 30) {
        const st = useStore.getState()
        const next = st.tf + acc * st.speed * 0.7
        useStore.setState({ tf: next > LAST ? 0 : next })
        acc = 0
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing])
  const at = (clientX: number) => {
    const r = bar.current!.getBoundingClientRect()
    return Math.min(Math.max(((clientX - r.left) / r.width) * LAST, 0), LAST)
  }
  const seek = (clientX: number) => set({ tf: Math.round(at(clientX) * 4) / 4, playing: false })
  const pct = (t: number) => `${(t / LAST) * 100}%`
  const day = Math.floor(tf + 1e-6)
  const hours = Math.round((tf - day) * 24)
  const label = (t: number) => {
    const d = Math.floor(t + 1e-6), h = Math.round((t - d) * 24)
    return `${dayName(doy, d + 1, weekday, true)}${h ? ` +${h} h` : ''}`
  }
  return (
    <footer className="tline panel" data-ui>
      <button className="play" onClick={() => set({ playing: !playing })} aria-label={playing ? 'Pause' : 'Play'}>{playing ? <IconPause /> : <IconPlay />}</button>
      <div className="mid">
        <div className="now">
          <b>{dayName(doy, day + 1, weekday)}</b>
          <span>{dayLabel(doy, day + 1)}{hours ? ` · +${hours} h` : ''}</span>
          <em>Day +{(tf + 1).toFixed(tf % 1 ? 1 : 0)}</em>
        </div>
        <div className="ticks" ref={bar}
          onPointerDown={(e) => { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); seek(e.clientX) }}
          onPointerMove={(e) => { setHover(at(e.clientX)); if (e.buttons) seek(e.clientX) }}
          onPointerLeave={() => setHover(null)}>
          {TICKS.map((t) => (
            <i key={t} className={`${t % 1 === 0 ? 'major' : ''} ${t <= tf + 1e-6 ? 'past' : ''}`} style={{ left: pct(t) }} />
          ))}
          {Array.from({ length: LAST + 1 }, (_, d) => (
            <span key={d} className={`dl ${d === day ? 'on' : ''}`} style={{ left: pct(d) }}>{dayName(doy, d + 1, weekday, true).split(' ')[0]}</span>
          ))}
          <b className="cur" style={{ left: pct(tf) }} />
          {hover !== null && <span className="tip" style={{ left: pct(hover) }}>{label(Math.round(hover * 4) / 4)}</span>}
        </div>
      </div>
      <div className="right">
        <button className="spd" onClick={() => set({ speed: speed >= 2 ? 0.5 : speed * 2 })} title="Playback speed">{speed}×</button>
        <button className="skip" onClick={() => set({ tf: 0, playing: false })} aria-label="Back to the first day" title="Back to the first day"><IconSkipBack /></button>
      </div>
    </footer>
  )
}
