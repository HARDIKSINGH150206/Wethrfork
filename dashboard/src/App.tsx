import { useEffect } from 'react'
import { MapView } from './components/map/MapView'
import { About } from './components/tabs/About'
import { TimelinePrime } from './components/tabs/TimelinePrime'
import { Validation } from './components/tabs/Validation'
import { TopBar } from './components/TopBar'
import { useStore } from './state/store'

export default function App() {
  const boot = useStore((s) => s.boot)
  const tab = useStore((s) => s.tab)
  useEffect(() => { void boot() }, [boot])
  return (
    <div className="app">
      <TopBar />
      <div className="body">
        {tab === 'map' && <MapView />}
        {tab === 'timeline' && <TimelinePrime />}
        {tab === 'validation' && <Validation />}
        {tab === 'about' && <About />}
      </div>
    </div>
  )
}
