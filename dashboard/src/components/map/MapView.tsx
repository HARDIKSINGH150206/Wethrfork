import { Drawer } from './Drawer'
import { Attribution, Coords, Legend, ModelPicker, ScaleBar } from './Legend'
import { MapStage } from './MapStage'
import { Meteogram } from './Meteogram'
import { Rail } from './Rail'
import { Sidebar } from './Sidebar'
import { Timeline } from './Timeline'
import { useStore } from '../../state/store'

export function MapView() {
  const meteo = useStore((s) => s.meteo && !!s.pin)
  const startError = useStore((s) => s.startError)
  return (
    <div className={`mapview ${meteo ? 'with-meteo' : ''}`}>
      <MapStage />
      {startError && (
        <div className="empty panel" data-ui role="alert">
          <b>Cannot load a start state</b>
          <p>{startError}</p>
          <small>The forecast server alone is not enough for the dashboard: it also needs the lab server and the local dataset (data/india_climate_train.nc).</small>
        </div>
      )}
      <Sidebar />
      <Drawer />
      <Rail />
      {meteo && <Meteogram />}
      <div className="bl" data-ui><Legend /><Coords /></div>
      <div className="br" data-ui><ModelPicker /></div>
      <ScaleBar />
      <Timeline />
      <Attribution />
    </div>
  )
}
