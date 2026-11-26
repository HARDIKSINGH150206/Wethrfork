import { useEffect, useRef } from 'react'
import { IconPause, IconPlay } from '../icons'
import { dayLabel, dayName } from '../../lib/dates'
import { useStore } from '../../state/store'

/** Bottom timeline: play button, one segment per forecast day, a bubble above the handle. */
export function Timeline() {
  const { tf, playing, speed, set, doy, weekday } = useStore()
  const bar = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!playing) return
    let raf = 0, last = performance.now(), acc = 0
    const tick = (now: number) => {
      acc += (now - last) / 1000; last = now
      if (acc > 1 / 30) {
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
  const seek = (clientX: number) => {
    const r = bar.current!.getBoundingClientRect()
    set({ tf: Math.min(Math.max(((clientX - r.left) / r.width) * 10 - 0.5, 0), 9), playing: false })
  }
  const pos = ((tf + 0.5) / 10) * 100
  return (
    <footer className="tline" data-ui>
      <button className="play" onClick={() => set({ playing: !playing })} aria-label={playing ? 'Pause' : 'Play'}>{playing ? <IconPause /> : <IconPlay />}</button>
      <div className="bar" ref={bar} onPointerDown={(e) => { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); seek(e.clientX) }} onPointerMove={(e) => { if (e.buttons) seek(e.clientX) }}>
        <div className="past" style={{ width: `${pos}%` }} />
        {Array.from({ length: 10 }, (_, d) => (
          <div key={d} className={`seg ${Math.round(tf) === d ? 'on' : ''}`}><span className="long">{dayName(doy, d + 1, weekday)}</span><span className="short">{dayName(doy, d + 1, weekday, true)}</span></div>
        ))}
        <div className="bub" style={{ left: `${pos}%` }}>{dayName(doy, Math.round(tf) + 1, weekday, true)} · {dayLabel(doy, Math.round(tf) + 1)} · +{(tf + 1).toFixed(1)} d</div>
      </div>
      <button className="spd" onClick={() => set({ speed: speed >= 2 ? 0.5 : speed * 2 })} title="Playback speed">{speed}×</button>
    </footer>
  )
}
