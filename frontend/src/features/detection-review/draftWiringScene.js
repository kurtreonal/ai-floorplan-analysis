import { devicePlacement, deviceConnector } from '../viewer-3d/devicePlacement.js'
import { connectionLead } from '../viewer-3d/connectionGeometry.js'
import { wiringComponents } from './connectedWiring.js'

// Advisory projection of the SAME draft source points, never a circuit or quantity input.
export function draftWiringScene(wires, scene) {
  const networks=wiringComponents(wires || [])
  const attachedDrops = new Set()
  const attachmentSegments = new Set()
  return (wires || []).filter(wire => wire.disposition !== 'rejected').flatMap(wire => {
    if (!Array.isArray(wire.points) || wire.points.length < 2 || wire.points.length > 2048
      || wire.points.some(p => !Number.isFinite(p.x) || !Number.isFinite(p.y) || p.x < 0 || p.y < 0
        || p.x * scene.sourceScale > scene.width || p.y * scene.sourceScale > scene.depth)) return []
    const knownAbsolute = Number.isFinite(wire.elevation_meters)
    const underFloor = wire.installation_method === 'concealed_under_floor'
    // No installation depth is inferred from dashes. Use the floor reference
    // until an actual depth is supplied, rather than mislabeling it as ceiling.
    const knownFloor = Number.isFinite(scene.floorElevationMeters)
    const relative=Number.isFinite(wire.height_above_floor_meters) ? wire.height_above_floor_meters
      : !knownAbsolute && underFloor ? 0
      : !knownAbsolute && (scene.automaticHeights ? wire.installation_method==='concealed_in_ceiling':!underFloor) && Number.isFinite(scene.serviceHeightAboveFloor) ? scene.serviceHeightAboveFloor:null
    const knownHeight=relative!==null || knownAbsolute && knownFloor
    const elevation = relative!==null ? relative*scene.unitsPerMeter:knownAbsolute ? (wire.elevation_meters - (knownFloor ? scene.floorElevationMeters : 0)) * scene.unitsPerMeter : underFloor ? 0 : scene.ceilingElevation
    const points = wire.points.map(p => [p.x * scene.sourceScale, elevation, p.y * scene.sourceScale])
    const segments = points.slice(1).map((end, index) => ({ start: points[index], end }))
    // Connections come only from shared draft attachments, never Three.js
    // proximity. Missing dimensions use labelled illustrative geometry only.
    const attachedDevices = new Set()
    const unmeasuredDevices = new Set()
    for (const attachment of wire.device_attachments || []) {
      const index = attachment.point_index
      const endpoint = points[index]
      const symbol = scene.symbols.find(s => s.id === attachment.symbol_id)
      if (!endpoint || !symbol?.presentation) continue
      const placement = devicePlacement(symbol, scene, symbol.presentation.family)
      if (attachedDevices.has(symbol.id) || placement.mount === 'plan') continue
      const measured=knownHeight && Number.isFinite(symbol.installation?.elevation_meters)
      attachedDevices.add(symbol.id)
      if (wire.source_evidence_required && !measured) {
        unmeasuredDevices.add(symbol.id)
        if (!scene.planningMountingHeights) continue // No unlabelled invented elevations.
      }
      const connector = deviceConnector(placement)
      for (const {start,end,vertical} of connectionLead(endpoint,connector)) {
        const dropKey = `${symbol.id}:${elevation}`
        const segmentKey = JSON.stringify([symbol.id,elevation,start,end])
        // Branches keep their individual horizontal attachment; a shared device
        // needs one rise/drop, not coincident cylinders from every touching wire.
        if (attachmentSegments.has(segmentKey) || (vertical && attachedDrops.has(dropKey))) continue
        if (Math.hypot(...end.map((v,i) => v-start[i])) > 1e-8) {
          segments.push({ start, end, previewDrop: vertical, deviceId: symbol.id,
            illustrative: !measured,
            provenance: 'explicit_device_attachment' })
          if (vertical) attachedDrops.add(dropKey)
          attachmentSegments.add(segmentKey)
        }
      }
    }
    return [{ id: wire.id, networkId:networks.get(wire.id), points, segments, connectionAnchors:[...(wire.device_attachments || []),...(wire.junction_attachments || [])].map(a => points[a.point_index]).filter(Boolean),
      deviceIds:[...attachedDevices], unmeasuredDeviceIds:[...unmeasuredDevices], illustrativeHeight: !knownHeight,
      installationMethod: wire.installation_method ?? 'unknown', lineStyle: wire.line_style ?? 'unknown',
      ...(wire.assignment_state ? {assignment_state:wire.assignment_state} : {}),
      ...(wire.origin === 'generated' ? { origin: 'generated' } : wire.path_origin === 'manual' ? {origin:'manual'} : {}) }]
  })
}

export function moveDraftWirePoint(wire, index, point, width, height) {
  if (!wire || !Number.isInteger(index) || index < 0 || index >= wire.points.length
    || ![point.x, point.y].every(Number.isFinite)) return null
  const next = { x: Math.round(Math.max(0, Math.min(width, point.x))), y: Math.round(Math.max(0, Math.min(height, point.y))) }
  if (wire.points.some((p,i) => i !== index && Math.abs(i-index) === 1 && p.x === next.x && p.y === next.y)) return null
  return { ...wire, points: wire.points.map((p,i) => i === index ? next : p),
    disposition: wire.disposition === 'added' ? 'added' : 'corrected',
    ...(wire.origin === 'generated' ? {suppression_reason:null} : {}) }
}
