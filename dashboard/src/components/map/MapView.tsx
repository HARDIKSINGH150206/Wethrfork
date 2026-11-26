import { Drawer } from './Drawer'
import { Legend } from './Legend'
import { LayerMenu } from './LayerMenu'
import { MapStage } from './MapStage'
import { Timeline } from './Timeline'

export function MapView() {
  return (
    <div className="mapview">
      <MapStage />
      <Drawer />
      <LayerMenu />
      <Legend />
      <Timeline />
    </div>
  )
}
