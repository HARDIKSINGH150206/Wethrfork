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
  return (
    <div className={`mapview ${meteo ? 'with-meteo' : ''}`}>
      <MapStage />
      <TopLeft />
      <Drawer />
      <LayerMenu />
      <Legend />
      {meteo && <Meteogram />}
      <Timeline />
      <div className="credit" data-ui>Wethrfork {meta?.model_name.replace('wethrfork-', '').replace('-speedlimit', '') ?? ''} · model domain 6–38°N 65–101°E · ERA5 (C3S) via WeatherBench 2</div>
    </div>
  )
}
