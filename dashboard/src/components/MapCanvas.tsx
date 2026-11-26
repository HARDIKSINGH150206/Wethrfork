import { useEffect, useRef, useState } from 'react'
import type { Scale } from '../lib/colors'
import { NLAT, NLON, latOf, lonOf } from '../lib/grid'

interface Props {
  data: Float32Array | null
  scale: Scale
  title: string
  box?: [number, number, number, number] | null
  ring?: Uint8Array | null // cells inside the speed-limit radius (judge)
  hard?: Uint8Array | null // cells inside our hard reach
  outline?: number[][] | null
  stipple?: Uint8Array | null
}

const W = 360
const H = 320

export function MapCanvas({ data, scale, title, box, ring, hard, outline, stipple }: Props) {
  const ref = useRef<HTMLCanvasElement>(null)
  const [hover, setHover] = useState<string>('')

  useEffect(() => {
    const c = ref.current
    if (!c) return
    const g = c.getContext('2d')!
    const cw = W / NLON
    const ch = H / NLAT
    g.clearRect(0, 0, W, H)
    g.fillStyle = '#10151c'
    g.fillRect(0, 0, W, H)
    if (data) {
      for (let i = 0; i < NLAT; i++)
        for (let j = 0; j < NLON; j++) {
          const v = scale.convert(data[i * NLON + j])
          const [r, gg, b] = scale.color(v)
          g.fillStyle = `rgb(${r | 0},${gg | 0},${b | 0})`
          g.fillRect(j * cw, (NLAT - 1 - i) * ch, cw + 0.5, ch + 0.5)
        }
    }
    const edge = (mask: Uint8Array, style: string, dash: number[]) => {
      g.strokeStyle = style
      g.setLineDash(dash)
      g.lineWidth = 1.5
      g.beginPath()
      for (let i = 0; i < NLAT; i++)
        for (let j = 0; j < NLON; j++) {
          if (!mask[i * NLON + j]) continue
          const x = j * cw, y = (NLAT - 1 - i) * ch
          if (i === NLAT - 1 || !mask[(i + 1) * NLON + j]) { g.moveTo(x, y); g.lineTo(x + cw, y) }
          if (i === 0 || !mask[(i - 1) * NLON + j]) { g.moveTo(x, y + ch); g.lineTo(x + cw, y + ch) }
          if (j === 0 || !mask[i * NLON + j - 1]) { g.moveTo(x, y); g.lineTo(x, y + ch) }
          if (j === NLON - 1 || !mask[i * NLON + j + 1]) { g.moveTo(x + cw, y); g.lineTo(x + cw, y + ch) }
        }
      g.stroke()
      g.setLineDash([])
    }
    if (stipple) {
      g.fillStyle = 'rgba(0,0,0,0.55)'
      for (let i = 0; i < NLAT; i++)
        for (let j = 0; j < NLON; j++) if (stipple[i * NLON + j]) g.fillRect(j * cw + cw / 2 - 1, (NLAT - 1 - i) * ch + ch / 2 - 1, 2, 2)
    }
    if (outline) {
      g.strokeStyle = 'rgba(255,255,255,0.75)'
      g.lineWidth = 1
      g.beginPath()
      outline.forEach(([lon, lat], k) => {
        const x = ((lon - (lonOf(0) - 0.5)) / NLON) * W
        const y = H - ((lat - (latOf(0) - 0.5)) / NLAT) * H
        if (k === 0) g.moveTo(x, y)
        else g.lineTo(x, y)
      })
      g.stroke()
    }
    if (ring) edge(ring, '#ffd24d', [5, 4])
    if (hard) edge(hard, '#ff7b54', [2, 3])
    if (box) {
      const x0 = (box[2] - 0.5 - (lonOf(0) - 0.5)) / NLON * W
      const x1 = (box[3] + 0.5 - (lonOf(0) - 0.5)) / NLON * W
      const y0 = H - (box[1] + 0.5 - (latOf(0) - 0.5)) / NLAT * H
      const y1 = H - (box[0] - 0.5 - (latOf(0) - 0.5)) / NLAT * H
      g.strokeStyle = '#ffffff'
      g.lineWidth = 2
      g.strokeRect(x0, y0, x1 - x0, y1 - y0)
    }
  }, [data, scale, box, ring, hard, outline, stipple])

  const onMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!data) return
    const r = e.currentTarget.getBoundingClientRect()
    const j = Math.floor(((e.clientX - r.left) / r.width) * NLON)
    const i = NLAT - 1 - Math.floor(((e.clientY - r.top) / r.height) * NLAT)
    if (i < 0 || j < 0 || i >= NLAT || j >= NLON) return
    setHover(`${latOf(i).toFixed(1)}°N ${lonOf(j).toFixed(1)}°E: ${scale.convert(data[i * NLON + j]).toFixed(2)} ${scale.unit}`)
  }

  return (
    <figure className="map">
      <figcaption>{title}</figcaption>
      <canvas ref={ref} width={W} height={H} onMouseMove={onMove} onMouseLeave={() => setHover('')} />
      <div className="hover">{hover || ' '}</div>
    </figure>
  )
}
