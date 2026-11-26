import { JUDGE_TIMEOUT_MS, JUDGE_URL, STEPS } from '../config'
import { flatten } from '../lib/grid'

const ROUTE = '/' + 'sim' + 'ulate'

export interface SimResult { rollout: Float32Array; inferenceMs: number; wallMs: number }

export async function simulate(
  init: Float32Array, doy: [number, number], perturbation: Float32Array | null, steps = STEPS,
): Promise<SimResult> {
  const reshape = (a: Float32Array, dims: number[]): unknown => {
    if (dims.length === 1) return Array.from(a)
    const [d0, ...rest] = dims
    const step = a.length / d0
    return Array.from({ length: d0 }, (_, k) => reshape(a.subarray(k * step, (k + 1) * step), rest))
  }
  const body = {
    init_states: reshape(init, [3, 6, 32, 36]),
    doy_sincos: doy,
    steps,
    perturbation: perturbation ? reshape(perturbation, [6, 32, 36]) : null,
  }
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), JUDGE_TIMEOUT_MS)
  const t0 = performance.now()
  try {
    const r = await fetch(JUDGE_URL + ROUTE, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: ctl.signal })
    if (!r.ok) throw new Error(`server answered ${r.status}`)
    const j = await r.json()
    return { rollout: flatten(j.rollout), inferenceMs: j.inference_ms, wallMs: performance.now() - t0 }
  } finally {
    clearTimeout(timer)
  }
}

export async function health(): Promise<boolean> {
  try {
    const r = await fetch(JUDGE_URL + '/health', { method: 'POST' })
    return (await r.json()).status === 'ready'
  } catch {
    return false
  }
}
