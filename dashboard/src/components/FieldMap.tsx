import { useEffect, useMemo, useRef, useState } from 'react'
import type { LayerDef } from '../lib/layers'
import { LAYERS } from '../lib/layers'
import { coastline, makeRaster, paintBase, paintField, RH, RW } from '../lib/render'
import type { Polyline } from '../lib/render'
import { useStore } from '../state/store'

interface Props {
  data: Float32Array | null
  layer?: LayerDef
  dmax?: number | null // set for a diverging (delta) field
  title: string
  note?: string
  outline?: Polyline | null
}

/** A small static map of one field with the shared base map, coastlines and outline. */
export function FieldMap({ data, layer = LAYERS.temp, dmax = null, title, note, outline = null }: Props) {
  const ref = useRef<HTMLCanvasElement>(null)
  const meta = useStore((s) => s.meta)
  const base = useMemo(() => makeRaster(), [])
  const fld = useMemo(() => makeRaster(), [])
  const coast = useMemo(() => (meta ? coastline(meta.land_sea_mask) : []), [meta])
  useEffect(() => {
    const cv = ref.current
    if (!cv || !meta) return
    paintBase(base, meta.land_sea_mask, meta.orography_m)
    const g = cv.getContext('2d')!
    cv.width = RW; cv.height = RH
    g.imageSmoothingEnabled = true
    g.drawImage(base, 0, 0)
    if (data) { paintField(fld, data, layer, dmax); g.drawImage(fld, 0, 0) }
    const line = (pl: Polyline, close = false) => {
      g.beginPath()
      pl.forEach(([lon, lat], k) => { const x = (lon - 65) * (RW / 36), y = (38 - lat) * (RH / 32); if (k) g.lineTo(x, y); else g.moveTo(x, y) })
      if (close) g.closePath()
      g.stroke()
    }
    g.lineWidth = 1; g.strokeStyle = 'rgba(255,255,255,0.22)'; coast.forEach((l) => line(l))
    if (outline) { g.lineWidth = 1.6; g.strokeStyle = 'rgba(255,255,255,0.7)'; line(outline, true) }
  }, [data, layer, dmax, meta, base, fld, coast, outline])
  return (
    <figure className="fieldmap">
      <figcaption>{title}</figcaption>
      <canvas ref={ref} />
      {note && <small>{note}</small>}
    </figure>
  )
}

export function useOutline(): Polyline | null {
  const [o, setO] = useState<Polyline | null>(null)
  useEffect(() => {
    fetch('/india_outline.geojson').then((r) => r.json()).then((g) => setO(g.features[0].geometry.coordinates[0])).catch(() => null)
  }, [])
  return o
}
