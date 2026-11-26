import { LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, sample } from './interp'
import type { View } from './view'
import { projX, projY } from './view'

const M_PER_DEG = 111200

/** Wind particles advected through a (u, v) field in m/s; positions live in degrees so zooming is free. */
export class ParticleSystem {
  private lon: Float32Array
  private lat: Float32Array
  private age: Float32Array
  private px: Float32Array
  private py: Float32Array
  private n: number
  private maxAge = 110

  constructor(n = 7000) {
    this.n = n
    this.lon = new Float32Array(n); this.lat = new Float32Array(n); this.age = new Float32Array(n)
    this.px = new Float32Array(n); this.py = new Float32Array(n)
    for (let i = 0; i < n; i++) this.spawn(i, true)
  }

  private spawn(i: number, randomAge = false) {
    this.lon[i] = LON_MIN + Math.random() * (LON_MAX - LON_MIN)
    this.lat[i] = LAT_MIN + Math.random() * (LAT_MAX - LAT_MIN)
    this.age[i] = randomAge ? Math.random() * this.maxAge : 0
    this.px[i] = NaN
  }

  reset() { for (let i = 0; i < this.n; i++) this.px[i] = NaN }

  /** Advance and draw one frame. `visSeconds` is how much simulated time one frame stands for. */
  step(g: CanvasRenderingContext2D, u: Float32Array, v: Float32Array, view: View, dpr: number, visSeconds = 2400) {
    g.lineWidth = 0.95 * dpr
    for (let i = 0; i < this.n; i++) {
      if (++this.age[i] > this.maxAge) { this.spawn(i); continue }
      const lat = this.lat[i], lon = this.lon[i]
      const uu = sample(u, lat, lon), vv = sample(v, lat, lon)
      const sp = Math.hypot(uu, vv)
      const dlon = (uu * visSeconds) / (M_PER_DEG * Math.cos((lat * Math.PI) / 180))
      const dlat = (vv * visSeconds) / M_PER_DEG
      const nl = lon + dlon, nt = lat + dlat
      if (nl < LON_MIN || nl > LON_MAX || nt < LAT_MIN || nt > LAT_MAX) { this.spawn(i); continue }
      const x0 = this.px[i], y0 = this.py[i]
      const x1 = projX(view, nl) * dpr, y1 = projY(view, nt) * dpr
      if (!Number.isNaN(x0)) {
        const a = Math.min(0.35 + sp / 16, 0.85)
        g.strokeStyle = `rgba(255,255,255,${a.toFixed(2)})`
        g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.stroke()
      }
      this.lon[i] = nl; this.lat[i] = nt; this.px[i] = x1; this.py[i] = y1
    }
  }
}
