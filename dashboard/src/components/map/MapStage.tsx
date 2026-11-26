import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CELLS } from '../../lib/grid'
import { LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, sample } from '../../lib/interp'
import { LAYERS, SENS_LAYER, scalarAt, windAt } from '../../lib/layers'
import { ParticleSystem } from '../../lib/particles'
import { coastline, contourLines, makeRaster, paintBase, paintField } from '../../lib/render'
import type { Polyline } from '../../lib/render'
import { deltaScale } from '../../lib/series'
import { CONTROL, useStore } from '../../state/store'
import type { View } from '../../lib/view'
import { fitView, panBy, projX, projY, unprojLat, unprojLon, zoomAt } from '../../lib/view'
import { PointPopup } from './PointPopup'

const snap = (v: number) => 6.5 + Math.round(v - 6.5)
const snapLon = (v: number) => 65.5 + Math.round(v - 65.5)

export function MapStage() {
  const wrap = useRef<HTMLDivElement>(null)
  const scene = useRef<HTMLCanvasElement>(null)
  const parts = useRef<HTMLCanvasElement>(null)
  const [size, setSize] = useState({ w: 800, h: 600 })
  const [view, setView] = useState<View>(() => fitView(800, 600))
  const viewRef = useRef(view)
  viewRef.current = view
  const [hover, setHover] = useState<{ x: number; y: number } | null>(null)
  const [outline, setOutline] = useState<Polyline | null>(null)
  const [dragBox, setDragBox] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null)

  const s = useStore()
  const { meta, universes, selected, layer, units, delta, compare, compareX, tf, showRings, showIsobars, showStipple, pin, sens, drawMode, drawnBox } = s
  const ctl = universes[CONTROL]?.rollout ?? null
  const uni = universes[selected]?.rollout ?? null
  const box = universes[selected]?.box ?? null

  // static layers prepared once
  const base = useMemo(() => makeRaster(), [])
  const rA = useMemo(() => makeRaster(), [])
  const rB = useMemo(() => makeRaster(), [])
  const rS = useMemo(() => makeRaster(), [])
  const coast = useMemo<Polyline[]>(() => (meta ? coastline(meta.land_sea_mask) : []), [meta])
  useEffect(() => { if (meta) paintBase(base, meta.land_sea_mask, meta.orography_m) }, [meta, base])
  useEffect(() => {
    fetch('/india_outline.geojson').then((r) => r.json()).then((g) => setOutline(g.features[0].geometry.coordinates[0])).catch(() => null)
  }, [])

  // sizing
  useEffect(() => {
    const el = wrap.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect()
      setSize({ w: r.width, h: r.height })
      setView(fitView(r.width, r.height))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const deltaMax = useMemo(() => (delta && ctl && uni && uni !== ctl ? deltaScale(uni, ctl, layer, LAYERS[layer].deltaFloor) : 1), [delta, ctl, uni, layer])
  const sigma = useMemo(() => (meta?.sigma_err ? Float32Array.from(meta.sigma_err.flat(3)) : null), [meta])

  // current fields kept for hover readouts
  const cur = useRef<{ a: Float32Array; b: Float32Array; pr: Float32Array } | null>(null)
  const isoKey = useRef('')
  const isoCache = useRef<ReturnType<typeof contourLines>>([])

  // ---------------------------------------------------------------- scene
  useEffect(() => {
    const cv = scene.current
    if (!cv) return
    const dpr = window.devicePixelRatio || 1
    cv.width = size.w * dpr; cv.height = size.h * dpr
    const g = cv.getContext('2d')!
    g.setTransform(dpr, 0, 0, dpr, 0, 0)
    g.fillStyle = '#08111d'
    g.fillRect(0, 0, size.w, size.h)
    const x0 = projX(view, LON_MIN), y0 = projY(view, LAT_MAX)
    const W = (LON_MAX - LON_MIN) * view.scale, H = (LAT_MAX - LAT_MIN) * view.scale
    g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high'
    g.drawImage(base, x0, y0, W, H)

    const def = LAYERS[layer]
    const aField = uni ? scalarAt(uni, tf, layer) : null
    const cField = ctl ? scalarAt(ctl, tf, layer) : null
    const isDelta = delta && aField && cField && uni !== ctl
    if (aField && cField) cur.current = { a: aField, b: cField, pr: cur.current?.pr ?? new Float32Array(CELLS) }

    const drawRaster = (cvs: HTMLCanvasElement) => g.drawImage(cvs, x0, y0, W, H)
    if (isDelta && aField && cField) {
      const d = new Float32Array(CELLS)
      for (let i = 0; i < CELLS; i++) d[i] = aField[i] - cField[i]
      paintField(rA, d, def, deltaMax)
      drawRaster(rA)
    } else if (compare && aField && cField) {
      paintField(rA, cField, def, null)
      paintField(rB, aField, def, null)
      const cx = compareX * size.w
      g.save(); g.beginPath(); g.rect(0, 0, cx, size.h); g.clip(); drawRaster(rA); g.restore()
      g.save(); g.beginPath(); g.rect(cx, 0, size.w - cx, size.h); g.clip(); drawRaster(rB); g.restore()
    } else if (aField) {
      paintField(rA, aField, def, null)
      drawRaster(rA)
    }
    if (sens) {
      const m = Float32Array.from(sens.map)
      const top = Array.from(m).sort((p, q) => p - q)[Math.floor(CELLS * 0.99)] || 1
      for (let i = 0; i < CELLS; i++) m[i] = Math.min(m[i] / top, 1)
      paintField(rS, m, SENS_LAYER, null)
      g.globalAlpha = 0.9; drawRaster(rS); g.globalAlpha = 1
    }

    // coastlines and the national outline
    const strokeLine = (pl: Polyline, close = false) => {
      g.beginPath()
      pl.forEach(([lon, lat], k) => (k ? g.lineTo(projX(view, lon), projY(view, lat)) : g.moveTo(projX(view, lon), projY(view, lat))))
      if (close) g.closePath()
      g.stroke()
    }
    g.lineWidth = 0.8; g.strokeStyle = 'rgba(255,255,255,0.22)'
    coast.forEach((l) => strokeLine(l))
    if (outline) { g.lineWidth = 1.4; g.strokeStyle = 'rgba(255,255,255,0.7)'; strokeLine(outline, true) }

    // graticule
    g.font = '10px system-ui'; g.fillStyle = 'rgba(200,215,235,0.55)'; g.strokeStyle = 'rgba(160,185,215,0.12)'; g.lineWidth = 1
    for (let lon = 70; lon <= 100; lon += 5) {
      const x = projX(view, lon); g.beginPath(); g.moveTo(x, y0); g.lineTo(x, y0 + H); g.stroke(); g.fillText(`${lon}°E`, x + 3, y0 + H - 4)
    }
    for (let lat = 10; lat <= 35; lat += 5) {
      const y = projY(view, lat); g.beginPath(); g.moveTo(x0, y); g.lineTo(x0 + W, y); g.stroke(); g.fillText(`${lat}°N`, x0 + 4, y - 3)
    }

    // isobars
    if (showIsobars && uni) {
      const key = `${selected}|${Math.round(tf * 4)}`
      if (key !== isoKey.current) {
        isoKey.current = key
        const levels: number[] = []
        for (let p = 98000; p <= 103600; p += 200) levels.push(p)
        isoCache.current = contourLines(scalarAt(uni, tf, 'pressure'), levels)
      }
      g.lineWidth = 1; g.strokeStyle = 'rgba(255,255,255,0.5)'; g.fillStyle = 'rgba(255,255,255,0.95)'; g.font = '600 10px system-ui'
      for (const c of isoCache.current) {
        const major = Math.round(c.level / 100) % 4 === 0
        g.lineWidth = major ? 1.3 : 0.7
        for (const ln of c.lines) {
          if (ln.length < 4) continue
          strokeLine(ln)
          if (major && ln.length > 24) {
            const mid = ln[Math.floor(ln.length / 2)]
            const lx = projX(view, mid[0]), ly = projY(view, mid[1])
            const txt = `${Math.round(c.level / 100)}`
            g.save(); g.lineWidth = 3; g.strokeStyle = 'rgba(8,17,29,0.8)'; g.strokeText(txt, lx - 8, ly + 3); g.fillText(txt, lx - 8, ly + 3); g.restore()
          }
        }
      }
    }

    // stippling where the response exceeds our measured forecast error
    if (showStipple && isDelta && aField && cField && sigma) {
      const ch = { temp: 0, rain: 1, pressure: 4, moisture: 5, wind: -1 }[layer]
      if (ch >= 0) {
        const lead = Math.min(Math.round(tf), 9)
        g.fillStyle = 'rgba(0,0,0,0.65)'
        for (let i = 0; i < 32; i++) for (let j = 0; j < 36; j++) {
          const k = i * 36 + j
          if (Math.abs(aField[k] - cField[k]) > sigma[(lead * 6 + ch) * CELLS + k]) g.fillRect(projX(view, 65.5 + j) - 1, projY(view, 6.5 + i) - 1, 2, 2)
        }
      }
    }

    // the speed limit
    if (box && selected !== CONTROL) {
      const day = Math.round(tf) + 1
      const ring = (r: number, color: string, dash: number[]) => {
        const a = projX(view, box[2] - 0.5 - r), b = projX(view, box[3] + 0.5 + r)
        const c2 = projY(view, box[1] + 0.5 + r), d2 = projY(view, box[0] - 0.5 - r)
        g.strokeStyle = color; g.setLineDash(dash); g.lineWidth = 1.6
        g.beginPath(); g.roundRect(a, c2, b - a, d2 - c2, r * view.scale); g.stroke(); g.setLineDash([])
      }
      if (showRings) { ring(3 + 8 * day, 'rgba(255,210,77,0.85)', [8, 6]); ring(8 * day, 'rgba(255,123,84,0.9)', [3, 5]) }
      g.strokeStyle = '#fff'; g.lineWidth = 2
      g.strokeRect(projX(view, box[2] - 0.5), projY(view, box[1] + 0.5), (box[3] - box[2] + 1) * view.scale, (box[1] - box[0] + 1) * view.scale)
    }
    if (drawnBox) {
      g.strokeStyle = '#4cc2ff'; g.lineWidth = 2; g.setLineDash([6, 4])
      g.strokeRect(projX(view, drawnBox[2] - 0.5), projY(view, drawnBox[1] + 0.5), (drawnBox[3] - drawnBox[2] + 1) * view.scale, (drawnBox[1] - drawnBox[0] + 1) * view.scale)
      g.setLineDash([])
    }
    if (compare && !isDelta) {
      g.font = '600 11px system-ui'; g.fillStyle = 'rgba(255,255,255,0.85)'
      g.fillText('CONTROL', 14, 86); g.fillText(`UNIVERSE · ${universes[selected]?.name ?? ''}`.toUpperCase(), compareX * size.w + 14, 86)
    }
  }, [view, size, layer, units, delta, compare, compareX, tf, selected, universes, showIsobars, showStipple, showRings, sens, drawnBox, deltaMax, meta, outline, coast, base, rA, rB, rS, sigma, uni, ctl, box])

  // ---------------------------------------------------------------- particles
  const sysA = useRef(new ParticleSystem()), sysB = useRef(new ParticleSystem())
  const ua = useRef(new Float32Array(CELLS)), va = useRef(new Float32Array(CELLS))
  const ub = useRef(new Float32Array(CELLS)), vb = useRef(new Float32Array(CELLS))
  useEffect(() => { sysA.current.reset(); sysB.current.reset() }, [view, size, compare])
  useEffect(() => {
    const cv = parts.current
    if (!cv) return
    const dpr = window.devicePixelRatio || 1
    cv.width = size.w * dpr; cv.height = size.h * dpr
    let raf = 0
    const g = cv.getContext('2d')!
    const tick = () => {
      const st = useStore.getState()
      g.globalCompositeOperation = 'destination-in'
      g.fillStyle = 'rgba(0,0,0,0.9)'
      g.fillRect(0, 0, cv.width, cv.height)
      g.globalCompositeOperation = 'source-over'
      const u0 = st.universes[st.selected]?.rollout, c0 = st.universes[CONTROL]?.rollout
      if (st.showParticles && st.tab === 'map' && u0 && c0) {
        const v = viewRef.current
        if (st.compare && !st.delta) {
          const cx = st.compareX * cv.width
          windAt(c0, st.tf, ub.current, vb.current); windAt(u0, st.tf, ua.current, va.current)
          g.save(); g.beginPath(); g.rect(0, 0, cx, cv.height); g.clip(); sysB.current.step(g, ub.current, vb.current, v, dpr); g.restore()
          g.save(); g.beginPath(); g.rect(cx, 0, cv.width - cx, cv.height); g.clip(); sysA.current.step(g, ua.current, va.current, v, dpr); g.restore()
        } else {
          windAt(u0, st.tf, ua.current, va.current)
          sysA.current.step(g, ua.current, va.current, v, dpr)
        }
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [size])

  // ---------------------------------------------------------------- interaction
  const drag = useRef<{ x: number; y: number; moved: boolean; mode: 'pan' | 'draw' } | null>(null)
  const rel = (e: React.PointerEvent | React.WheelEvent | React.MouseEvent) => {
    const r = wrap.current!.getBoundingClientRect()
    return { x: e.clientX - r.left, y: e.clientY - r.top }
  }
  const onWheel = useCallback((e: React.WheelEvent) => {
    const p = rel(e)
    setView((v) => zoomAt(v, p.x, p.y, Math.exp(-e.deltaY * 0.0015)))
  }, [])
  const onDown = (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest('[data-ui]')) return
    const p = rel(e)
    drag.current = { x: p.x, y: p.y, moved: false, mode: drawMode ? 'draw' : 'pan' }
    wrap.current!.setPointerCapture(e.pointerId)
    if (drawMode) setDragBox({ x0: p.x, y0: p.y, x1: p.x, y1: p.y })
  }
  const onMove = (e: React.PointerEvent) => {
    const p = rel(e)
    setHover(p)
    const d = drag.current
    if (!d) return
    if (Math.abs(p.x - d.x) + Math.abs(p.y - d.y) > 3) d.moved = true
    if (d.mode === 'pan') { setView((v) => panBy(v, p.x - d.x, p.y - d.y)); d.x = p.x; d.y = p.y }
    else setDragBox((b) => (b ? { ...b, x1: p.x, y1: p.y } : b))
  }
  const onUp = (e: React.PointerEvent) => {
    const d = drag.current
    drag.current = null
    if (!d) return
    const p = rel(e)
    const v = viewRef.current
    if (d.mode === 'draw' && dragBox) {
      const la = [unprojLat(v, dragBox.y0), unprojLat(v, p.y)], lo = [unprojLon(v, dragBox.x0), unprojLon(v, p.x)]
      setDragBox(null)
      if (d.moved) s.set({ drawnBox: [snap(Math.min(...la)), snap(Math.max(...la)), snapLon(Math.min(...lo)), snapLon(Math.max(...lo))], drawMode: false, drawer: 'shock' })
      return
    }
    if (!d.moved) {
      const lat = unprojLat(v, p.y), lon = unprojLon(v, p.x)
      if (lat >= LAT_MIN && lat <= LAT_MAX && lon >= LON_MIN && lon <= LON_MAX) s.set({ pin: { lat, lon }, sens: null })
    }
  }

  // hover readout
  const readout = useMemo(() => {
    if (!hover || !cur.current) return null
    const lat = unprojLat(view, hover.y), lon = unprojLon(view, hover.x)
    if (lat < LAT_MIN || lat > LAT_MAX || lon < LON_MIN || lon > LON_MAX) return null
    const def = LAYERS[layer]
    const a = sample(cur.current.a, lat, lon), b = sample(cur.current.b, lat, lon)
    return { lat, lon, a, b, text: def.fmt(a, units), dtext: selected !== CONTROL ? def.fmt(a - b, units, true) : null }
  }, [hover, view, layer, units, selected, tf, uni, ctl])

  const pinXY = pin ? { x: projX(view, pin.lon), y: projY(view, pin.lat) } : null
  const divX = compareX * size.w

  return (
    <div ref={wrap} className={`stage ${drawMode ? 'drawing' : ''}`} onWheel={onWheel} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={() => setHover(null)}
      onDoubleClick={(e) => { const p = rel(e); setView((v) => zoomAt(v, p.x, p.y, 1.8)) }}>
      <canvas ref={scene} style={{ width: size.w, height: size.h }} />
      <canvas ref={parts} style={{ width: size.w, height: size.h }} className="parts" />
      {hover && readout && (
        <>
          <div className="cross" style={{ left: hover.x, top: hover.y }} />
          <div className="readout" data-ui>
            <b>{readout.text}</b>
            {readout.dtext && <span className={readout.a - readout.b >= 0 ? 'up' : 'down'}> {readout.a - readout.b >= 0 ? '▲' : '▼'} {readout.dtext}</span>}
            <small>{readout.lat.toFixed(2)}°N {readout.lon.toFixed(2)}°E</small>
          </div>
        </>
      )}
      {compare && !delta && (
        <div className="divider" style={{ left: divX }} data-ui
          onPointerDown={(e) => { e.stopPropagation(); (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId) }}
          onPointerMove={(e) => { if (e.buttons) s.set({ compareX: Math.min(Math.max(rel(e).x / size.w, 0.08), 0.92) }) }}><i /></div>
      )}
      {dragBox && <div className="dragbox" style={{ left: Math.min(dragBox.x0, dragBox.x1), top: Math.min(dragBox.y0, dragBox.y1), width: Math.abs(dragBox.x1 - dragBox.x0), height: Math.abs(dragBox.y1 - dragBox.y0) }} />}
      {pinXY && <div className="pin" style={{ left: pinXY.x, top: pinXY.y }}><span /></div>}
      {pin && pinXY && <PointPopup pin={pin} x={pinXY.x} y={pinXY.y} bounds={size} />}
      <div className="zoom" data-ui>
        <button onClick={() => setView((v) => zoomAt(v, size.w / 2, size.h / 2, 1.5))} aria-label="Zoom in">+</button>
        <button onClick={() => setView((v) => zoomAt(v, size.w / 2, size.h / 2, 1 / 1.5))} aria-label="Zoom out">−</button>
        <button onClick={() => setView(fitView(size.w, size.h))} aria-label="Fit">⌖</button>
      </div>
    </div>
  )
}
