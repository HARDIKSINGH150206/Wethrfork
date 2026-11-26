import { Drawer } from './Drawer'
import { Legend } from './Legend'
import { LayerMenu } from './LayerMenu'
import { MapStage } from './MapStage'
import { Meteogram } from './Meteogram'
import { Timeline } from './Timeline'
import { TopLeft } from './TopLeft'
import { useStore } from '../../state/store'

export function MapView() {
  const meteo = useStore((s) => s.meteo && !!s.pin)
  const meta = useStore((s) => s.meta)
  const startError = useStore((s) => s.startError)
  return (
    <div className={`mapview ${meteo ? 'with-meteo' : ''}`}>
      <MapStage />
      {startError && (
        <div className="empty" data-ui role="alert">
          <b>Cannot load a start state</b>
          <p>{startError}</p>
          <small>The forecast server alone is not enough for the dashboard: it also needs the lab server and the local dataset (data/india_climate_train.nc).</small>
        </div>
      )}
      <TopLeft />
      <Drawer />
      <LayerMenu />
      <Legend />
      {meteo && <Meteogram />}
      <Timeline />
      <div className="brand" data-ui>
        <svg width="22" height="22" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="rgba(255,255,255,0.9)" /><path d="M7 10l4 12 5-9 5 9 4-12" stroke="#2b2b2b" strokeWidth="2.8" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
        <b>wethrfork</b>
      </div>
      <div className="credit" data-ui>Wethrfork {meta?.model_name.replace('wethrfork-', '').replace('-speedlimit', '') ?? ''} · model domain 6–38°N 65–101°E · ERA5 (C3S) via WeatherBench 2</div>
    </div>
  )
}
