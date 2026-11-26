import { useEffect } from 'react'
import { MapView } from './components/map/MapView'
import { About } from './components/tabs/About'
import { TimelinePrime } from './components/tabs/TimelinePrime'
import { Validation } from './components/tabs/Validation'
import { useStore } from './state/store'

export default function App() {
  const boot = useStore((s) => s.boot)
  const tab = useStore((s) => s.tab)
  const set = useStore((s) => s.set)
  useEffect(() => { void boot() }, [boot])
  return (
    <div className="app">
      <MapView />
      {tab !== 'map' && (
        <div className="sheet">
          <button className="sheetx" onClick={() => set({ tab: 'map' })} aria-label="Back to the map">← Map</button>
          {tab === 'timeline' && <TimelinePrime />}
          {tab === 'validation' && <Validation />}
          {tab === 'about' && <About />}
        </div>
      )}
    </div>
  )
}
