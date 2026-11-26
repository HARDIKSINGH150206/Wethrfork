import { LAB_TIMEOUT_MS, LAB_URL } from '../config'
import type { Meta, Verdict, WindowData, WindowInfo } from './types'

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), LAB_TIMEOUT_MS)
  try {
    const r = await fetch(LAB_URL + path, { ...init, signal: ctl.signal })
    if (!r.ok) throw new Error(`lab ${path} answered ${r.status}`)
    return (await r.json()) as T
  } finally {
    clearTimeout(timer)
  }
}

const post = (body: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const getMeta = () => call<Meta>('/meta')
export const getWindows = () => call<WindowInfo[]>('/windows')
export const getWindow = (id: string) => call<WindowData>(`/windows/${id}`)
export const getFuzz = () => call<Record<string, unknown>>('/fuzz')
export const getNatural = () => call<Record<string, unknown>>('/natural-experiment')
export const postVerdict = (b: { init_states: unknown; doy_sincos: number[]; perturbation: unknown; box: number[] | null; steps: number }) =>
  call<Verdict>('/verdict', post(b))
export const postSensitivity = (b: unknown) => call<{ grad: number[][][]; top_channel: string; elapsed_ms: number }>('/sensitivity', post(b))
