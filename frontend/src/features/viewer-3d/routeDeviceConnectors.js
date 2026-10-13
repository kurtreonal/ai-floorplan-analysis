import { devicePlacement, deviceConnector } from './devicePlacement.js'
import { deviceFamily } from '../detection-review/devicePresentation.js'

// Display-only leads from exact stored A* endpoints to the SAME mounted mesh.
// Never alter route measurements, canonical anchors, circuit membership or BOM.
export function routeDeviceConnectors(scene, segments) {
  if (!scene || scene.previewOnly || !Array.isArray(segments)) return []
  const leads = []
  for (const symbol of scene.symbols || []) {
    const installation = symbol.installation
    if (installation?.provenance !== 'designer_supplied_planning') continue
    const anchor = { x: symbol.position[0], y: symbol.position[2], elevation_meters: installation.elevation_meters }
    const touches = segments.some(s => [s.start,s.end].some(p => (installation.floor_id == null || p.floor_id === installation.floor_id)
      && p.x === anchor.x && p.y === anchor.y
      && p.elevation_meters === anchor.elevation_meters))
    if (!touches) continue
    const family = symbol.presentation?.family || deviceFamily(symbol.classification?.name)
    const placement = devicePlacement(symbol,scene,family)
    if (placement.mount === 'plan') continue
    const position = deviceConnector(placement)
    const end = { x: position[0], y: position[2], elevation_meters: position[1] }
    if (Math.hypot(end.x-anchor.x,end.y-anchor.y,end.elevation_meters-anchor.elevation_meters)>1e-8) {
      leads.push({ kind: 'device_connector', start: anchor, end, symbolId: symbol.id,
        provenance: 'display_attachment_not_measurement' })
    }
  }
  return leads
}
