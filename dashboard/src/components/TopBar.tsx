import { CHANNELS } from '../api/types'
import { useStore } from '../state/store'

export function TopBar() {
  const { windows, windowId, selectWindow, channel, setChannel, judgeOnline, labOnline, meta } = useStore()
  return (
    <header className="top">
      <h1>WETHRFORK <small>a weather model with a speed limit</small></h1>
      <label>window
        <select value={windowId ?? ''} onChange={(e) => selectWindow(e.target.value)}>
          {windows.map((w) => <option key={w.id} value={w.id}>{w.label}</option>)}
        </select>
      </label>
      <label>channel
        <select value={channel} onChange={(e) => setChannel(e.target.value as typeof channel)}>
          {CHANNELS.map((c) => <option key={c}>{c}</option>)}
        </select>
      </label>
      <span className={`badge ${judgeOnline ? 'on' : 'off'}`}>server {judgeOnline ? 'ready' : 'offline'}</span>
      <span className={`badge ${labOnline ? 'on' : 'off'}`}>lab {labOnline ? 'online' : 'offline'}</span>
      {meta && <span className="badge">{meta.model_name}</span>}
    </header>
  )
}
