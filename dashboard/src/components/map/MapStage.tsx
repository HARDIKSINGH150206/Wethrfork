import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CELLS } from '../../lib/grid'
import { LAT_MAX, LAT_MIN, LON_MAX, LON_MIN } from '../../lib/interp'
import type { LayerId } from '../../lib/layers'
import { LAYERS, SENS_LAYER, scalarAt, windAt } from '../../lib/layers'
import { ParticleSystem } from '../../lib/particles'
import { coastline, contourLines, makeRaster, paintBase, paintField, paintRelief } from '../../lib/render'
import type { Polyline } from '../../lib/render'
import { deltaScale } from '../../lib/series'
import { CONTROL, useStore } from '../../state/store'
import { useMap } from '../../state/mapctl'
import { clampView, coverView, fitView, panBy, projX, projY, unprojLat, unprojLon, zoomAt } from '../../lib/view'
import { PointPicker } from './PointPicker'
import { CITIES, SEAS } from '../../lib/cities'

const snap = (v: number) => 6.5 + Math.round(v - 6.5)
const snapLon = (v: number) => 65.5 + Math.round(v - 65.5)

/** System font stack only: the dashboard must work offline, so no web fonts are fetched. */
export const MAP_FONT = '"Museo Sans Rounded", Nunito, "Nunito Sans", "Segoe UI", "Noto Sans", Ubuntu, system-ui, sans-serif'
/** How much of the satellite base shows through each forecast layer (rain is transparent where it is dry). */
const FIELD_ALPHA: Record<LayerId, number> = { wind: 0.8, temp: 0.78, rain: 1, pressure: 0.74, moisture: 0.78 }
const OCEAN = '#0b1736'

interface Basemap { img: HTMLImageElement; extent: [number, number, number, number] } // lon0, lon1, lat0, lat1
interface Borders { coast: Polyline[]; border: Polyline[]; labels: { name: string; lon: number; lat: number; rank: number }[] }
const EXTRA_COUNTRIES = [{ name: 'CHINA', lon: 95, lat: 35.6, rank: 2 }]

export function MapStage() {
  const wrap = useRef<HTMLDivElement>(null)
  const scene = useRef<HTMLCanvasElement>(null)
  const parts = useRef<HTMLCanvasElement>(null)
  const [size, setSize] = useState({ w: 800, h: 600 })
  const view = useMap((m) => m.view)
  const setView = useMap((m) => m.setView)
  const setHover = useMap((m) => m.setHover)
  const viewRef = useRef(view)
  viewRef.current = view
  const [outline, setOutline] = useState<Polyline | null>(null)
  const [basemap, setBasemap] = useState<Basemap | null>(null)
  const [borders, setBorders] = useState<Borders | null>(null)
  const [dragBox, setDragBox] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null)

  const s = useStore()
  const { meta, universes, selected, layer, delta, compare, compareX, tf, showRings, showIsobars, showStipple, pin, sens, drawMode, drawnBox, focus } = s
  const ctl = universes[CONTROL]?.rollout ?? null
  const uni = universes[selected]?.rollout ?? null
  const box = universes[selected]?.box ?? null

  // static layers prepared once
  const base = useMemo(() => makeRaster(), [])
  const rA = useMemo(() => makeRaster(), [])
  const rB = useMemo(() => makeRaster(), [])
  const rS = useMemo(() => makeRaster(), [])
  const relief = useMemo(() => makeRaster(), [])
  const coast = useMemo<Polyline[]>(() => (meta ? coastline(meta.land_sea_mask) : []), [meta])
  useEffect(() => { if (meta) { paintBase(base, meta.land_sea_mask, meta.orography_m); paintRelief(relief, meta.orography_m) } }, [meta, base, relief])
  useEffect(() => {
    // Bundled, public-domain base map (scripts/build_basemap.py). The procedural base above is the fallback.
    const img = new Image()
    img.onload = () => setBasemap({ img, extent: [40, 126, -6, 52] })
    img.src = '/basemap.jpg'
    fetch('/borders.json').then((r) => r.json()).then((b: Borders & { extent: [number, number, number, number] }) => {
      setBorders(b)
      setBasemap((m) => (m ? { ...m, extent: b.extent } : m))
    }).catch(() => null)
    fetch('/india_outline.geojson').then((r) => r.json()).then((g) => setOutline(g.features[0].geometry.coordinates[0])).catch(() => null)
  }, [])

  // sizing
  useEffect(() => {
    const el = wrap.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect()
      setSize({ w: r.width, h: r.height })
      setView(coverView(r.width, r.height))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [setView])

  useEffect(() => {
    if (!focus) return
    setView((v) => {
      const base0 = fitView(v.w, v.h).scale
      return clampView({ ...v, scale: base0 * focus.zoom, cx: focus.lon, cy: focus.lat })
    })
  }, [focus, setView])

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
    g.fillStyle = OCEAN
    g.fillRect(0, 0, size.w, size.h)
    const x0 = projX(view, LON_MIN), y0 = projY(view, LAT_MAX)
    const W = (LON_MAX - LON_MIN) * view.scale, H = (LAT_MAX - LAT_MIN) * view.scale
    g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high'
    if (basemap) {
      const [l0, l1, b0, b1] = basemap.extent
      g.drawImage(basemap.img, projX(view, l0), projY(view, b1), (l1 - l0) * view.scale, (b1 - b0) * view.scale)
    } else {
      g.drawImage(base, x0, y0, W, H)
    }

    const def = LAYERS[layer]
    const aField = uni ? scalarAt(uni, tf, layer) : null
    const cField = ctl ? scalarAt(ctl, tf, layer) : null
    const isDelta = delta && aField && cField && uni !== ctl
    if (aField && cField) cur.current = { a: aField, b: cField, pr: cur.current?.pr ?? new Float32Array(CELLS) }

    const drawRaster = (cvs: HTMLCanvasElement) => g.drawImage(cvs, x0, y0, W, H)
    g.globalAlpha = isDelta ? 1 : FIELD_ALPHA[layer]
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
    g.globalAlpha = 1
    // without the satellite image, keep the old terrain relief through the colour layer
    if (!basemap) { g.save(); g.globalCompositeOperation = 'soft-light'; g.globalAlpha = 0.85; drawRaster(relief); g.restore() }
    if (sens) {
      const m = Float32Array.from(sens.map)
      const top = Array.from(m).sort((p, q) => p - q)[Math.floor(CELLS * 0.99)] || 1
      for (let i = 0; i < CELLS; i++) m[i] = Math.min(m[i] / top, 1)
      paintField(rS, m, SENS_LAYER, null)
      g.globalAlpha = 0.9; drawRaster(rS); g.globalAlpha = 1
    }

    // coastlines and borders
    const strokeLine = (pl: Polyline, close = false) => {
      g.beginPath()
      pl.forEach(([lon, lat], k) => (k ? g.lineTo(projX(view, lon), projY(view, lat)) : g.moveTo(projX(view, lon), projY(view, lat))))
      if (close) g.closePath()
      g.stroke()
    }
    g.lineJoin = 'round'; g.lineCap = 'round'
    if (borders) {
      g.lineWidth = 1; g.strokeStyle = 'rgba(255,255,255,0.62)'
      borders.coast.forEach((l) => strokeLine(l))
      g.lineWidth = 1; g.strokeStyle = 'rgba(255,255,255,0.78)'
      borders.border.forEach((l) => strokeLine(l))
    } else {
      g.lineWidth = 1; g.strokeStyle = 'rgba(255,255,255,0.5)'
      coast.forEach((l) => strokeLine(l))
      if (outline) { g.lineWidth = 1.3; g.strokeStyle = 'rgba(255,255,255,0.7)'; strokeLine(outline, true) }
    }

    // isobars
    if (showIsobars && uni) {
      const key = `${selected}|${Math.round(tf * 4)}`
      if (key !== isoKey.current) {
        isoKey.current = key
        const levels: number[] = []
        for (let p = 98000; p <= 103600; p += 400) levels.push(p)
        isoCache.current = contourLines(scalarAt(uni, tf, 'pressure'), levels)
      }
      g.lineWidth = 1; g.strokeStyle = 'rgba(255,255,255,0.55)'; g.fillStyle = 'rgba(255,255,255,0.95)'; g.font = `700 10px ${MAP_FONT}`
      for (const c of isoCache.current) {
        const major = Math.round(c.level / 100) % 8 === 0
        g.lineWidth = major ? 1.4 : 0.8
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

    // places, drawn last so they sit above every layer; greedy placement so labels never overlap
    const z = view.scale / fitView(size.w, size.h).scale
    const placed: [number, number, number, number][] = []
    const take = (x0: number, y0: number, x1: number, y1: number) => {
      if (x0 < 2 || y0 < 2 || x1 > size.w - 2 || y1 > size.h - 2) return false // whole label on screen, never cut at an edge
      for (const [a, b, c2, d] of placed) if (x0 < c2 && x1 > a && y0 < d && y1 > b) return false
      placed.push([x0 - 3, y0 - 2, x1 + 3, y1 + 2])
      return true
    }
    const ls = g as CanvasRenderingContext2D & { letterSpacing: string }
    const halo = (txt: string, x: number, y: number) => {
      g.shadowColor = 'rgba(0,0,0,0.85)'; g.shadowBlur = 4
      g.lineWidth = 2.6; g.strokeStyle = 'rgba(0,0,0,0.38)'; g.strokeText(txt, x, y)
      g.fillStyle = '#fff'; g.fillText(txt, x, y)
      g.shadowBlur = 0; g.shadowColor = 'transparent'
    }
    g.textBaseline = 'middle'; g.textAlign = 'center'
    const city = (c: (typeof CITIES)[number]) => {
      const cx = projX(view, c.lon), cy = projY(view, c.lat)
      g.font = `${c.rank === 1 ? 700 : 600} ${c.rank === 1 ? 13 : 12.5}px ${MAP_FONT}`; ls.letterSpacing = '0px'
      const w = g.measureText(c.name).width
      if (!take(cx - w / 2, cy - 18, cx + w / 2, cy + 3)) return
      halo(c.name, cx, cy - 10)
      g.beginPath(); g.arc(cx, cy, 2.4, 0, Math.PI * 2); g.fillStyle = '#fff'; g.fill()
      g.lineWidth = 1; g.strokeStyle = 'rgba(0,0,0,0.6)'; g.stroke()
    }
    const country = (c: { name: string; lon: number; lat: number }) => {
      const cx = projX(view, c.lon), cy = projY(view, c.lat)
      g.font = `800 13px ${MAP_FONT}`; ls.letterSpacing = '1.6px'
      const w = g.measureText(c.name).width
      if (take(cx - w / 2, cy - 8, cx + w / 2, cy + 8)) halo(c.name, cx, cy)
      ls.letterSpacing = '0px'
    }
    const countries = [...(borders?.labels ?? []), ...EXTRA_COUNTRIES].filter((c) => c.rank <= (z > 2 ? 5 : 4))
    CITIES.filter((c) => c.rank === 1).forEach(city)
    countries.forEach(country)
    CITIES.filter((c) => c.rank === 2).forEach(city)
    g.font = `italic 600 12.5px ${MAP_FONT}`; ls.letterSpacing = '0.6px'
    for (const s2 of SEAS) {
      const cx = projX(view, s2.lon), cy = projY(view, s2.lat), w = g.measureText(s2.name).width
      if (take(cx - w / 2, cy - 8, cx + w / 2, cy + 8)) { g.fillStyle = 'rgba(205,225,255,0.62)'; g.fillText(s2.name, cx, cy) }
    }
    ls.letterSpacing = '0px'
    if (z >= 2.2) CITIES.filter((c) => c.rank === 3).forEach(city)
    g.textBaseline = 'alphabetic'; g.textAlign = 'start'
    if (compare && !isDelta) {
      g.font = `800 11px ${MAP_FONT}`; g.fillStyle = 'rgba(255,255,255,0.9)'; ls.letterSpacing = '1px'
      g.fillText('CONTROL', compareX * size.w - 90, size.h - 112); g.fillText(`${universes[selected]?.name ?? ''}`.toUpperCase(), compareX * size.w + 14, size.h - 112)
      ls.letterSpacing = '0px'
    }
  }, [view, size, layer, delta, compare, compareX, tf, selected, universes, showIsobars, showStipple, showRings, sens, drawnBox, deltaMax, meta, outline, coast, base, rA, rB, rS, relief, sigma, uni, ctl, box, basemap, borders])

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
    setView((v) => clampView(zoomAt(v, p.x, p.y, Math.exp(-e.deltaY * 0.0015))))
  }, [setView])
  const onDown = (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest('[data-ui]')) return
    const p = rel(e)
    drag.current = { x: p.x, y: p.y, moved: false, mode: drawMode ? 'draw' : 'pan' }
    wrap.current!.setPointerCapture(e.pointerId)
    if (drawMode) setDragBox({ x0: p.x, y0: p.y, x1: p.x, y1: p.y })
    if (s.panel) s.set({ panel: null })
  }
  const onMove = (e: React.PointerEvent) => {
    const p = rel(e)
    const v = viewRef.current
    setHover({ lat: unprojLat(v, p.y), lon: unprojLon(v, p.x) })
    const d = drag.current
    if (!d) return
    if (Math.abs(p.x - d.x) + Math.abs(p.y - d.y) > 3) d.moved = true
    if (d.mode === 'pan') { setView((v2) => clampView(panBy(v2, p.x - d.x, p.y - d.y))); d.x = p.x; d.y = p.y }
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

  const pinXY = pin ? { x: projX(view, pin.lon), y: projY(view, pin.lat) } : null
  const divX = compareX * size.w

  return (
    <div ref={wrap} className={`stage ${drawMode ? 'drawing' : ''}`} onWheel={onWheel} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp}
      onPointerLeave={() => setHover(null)}
      onDoubleClick={(e) => { if ((e.target as HTMLElement).closest('[data-ui]')) return; const p = rel(e); setView((v) => clampView(zoomAt(v, p.x, p.y, 1.8))) }}>
      <canvas ref={scene} style={{ width: size.w, height: size.h }} />
      <canvas ref={parts} style={{ width: size.w, height: size.h }} className="parts" />
      {compare && !delta && (
        <div className="divider" style={{ left: divX }} data-ui
          onPointerDown={(e) => { e.stopPropagation(); (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId) }}
          onPointerMove={(e) => { if (e.buttons) s.set({ compareX: Math.min(Math.max(rel(e).x / size.w, 0.08), 0.92) }) }}><i /></div>
      )}
      {dragBox && <div className="dragbox" style={{ left: Math.min(dragBox.x0, dragBox.x1), top: Math.min(dragBox.y0, dragBox.y1), width: Math.abs(dragBox.x1 - dragBox.x0), height: Math.abs(dragBox.y1 - dragBox.y0) }} />}
      {pinXY && <div className="pin" style={{ left: pinXY.x, top: pinXY.y }}><span /></div>}
      {pin && pinXY && <PointPicker pin={pin} x={pinXY.x} y={pinXY.y} />}
    </div>
  )
}
