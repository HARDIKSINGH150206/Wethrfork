import { useEffect } from 'react'
import { ForkView } from './components/ForkView'
import { ImpactCards } from './components/ImpactCards'
import { LimitsVerdict } from './components/LimitsVerdict'
import { ShockComposer } from './components/ShockComposer'
import { TopBar } from './components/TopBar'
import { UniverseList } from './components/UniverseList'
import { useStore } from './state/store'

export default function App() {
  const boot = useStore((s) => s.boot)
  useEffect(() => { void boot() }, [boot])
  return (
    <div className="app">
      <TopBar />
      <aside>
        <ShockComposer />
        <UniverseList />
      </aside>
      <main>
        <ForkView />
        <div className="row">
          <LimitsVerdict />
          <ImpactCards />
        </div>
      </main>
    </div>
  )
}
