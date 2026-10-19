import { findWireDeviceTargets } from './deviceConnections.js'

// A preview is not connectivity: only the drag-end transaction commits a join.
export function findWireEndpointSnap(point, wireId, index, draft, presentations = {}, threshold = 14, deviceDistance = null, pathDistance = null) {
  const choices = findWireEndpointTargets(point, wireId, index, draft, presentations, threshold, deviceDistance, pathDistance)
  return choices.length === 1 ? choices[0] : null
}

// Equally near targets remain distinct. Only an explicit chooser action resolves
// ambiguity; stable sorting never grants connectivity to the first device ID.
export function findWireEndpointTargets(point, wireId, index, draft, presentations = {}, threshold = 14, deviceDistance = null, pathDistance = null) {
  if(!point || ![point.x,point.y,threshold].every(Number.isFinite) || threshold<0)return []
  const choices = findWireDeviceTargets(point, wireId, index, draft, presentations, threshold, deviceDistance).map(c => ({...c,kind:'device'}))
  const wire = draft.wirings.find(w => w.id === wireId)
  if (!wire || ![0, wire.points.length-1].includes(index) || wire.junction_attachments?.some(a => a.point_index === index)
    || wire.device_attachments?.some(a => a.point_index === index)) return nearestTargets(choices)
  for (const other of draft.wirings) {
    if (other.id === wireId || other.disposition === 'rejected' || other.suppression_reason
      || (wire.origin === 'generated') !== (other.origin === 'generated')
      || (wire.circuit_id ?? null) !== (other.circuit_id ?? null)
      || (wire.elevation_meters ?? null) !== (other.elevation_meters ?? null)
      || (wire.installation_method || 'unknown') !== (other.installation_method || 'unknown')) continue
    for (let edge = 0; edge < other.points.length-1; edge++) {
      const a = other.points[edge], b = other.points[edge+1], dx = b.x-a.x, dy = b.y-a.y
      if (!(dx*dx+dy*dy)) continue
      let t = Math.max(0,Math.min(1,((point.x-a.x)*dx+(point.y-a.y)*dy)/(dx*dx+dy*dy)))
      if (t < 1e-8) t = 0
      if (t > 1-1e-8) t = 1
      const target = {x:a.x+t*dx,y:a.y+t*dy}
      const vertex = t === 0 ? edge : t === 1 ? edge+1 : null
      if (other.points.length >= 2048 && vertex === null) continue
      if (other.device_attachments?.some(c => c.point_index === vertex)) continue
      const neighbor = wire.points[index === 0 ? 1 : index-1]
      if (neighbor.x === target.x && neighbor.y === target.y) continue
      const distance = pathDistance ? pathDistance(target,other) : Math.hypot(target.x-point.x,target.y-point.y)
      if (Number.isFinite(distance) && distance <= threshold) choices.push({kind:'junction',wireId:other.id,segmentIndex:edge,t,point:target,distance})
    }
  }
  return nearestTargets(choices)
}

function nearestTargets(choices) {
  choices.sort((a,b)=>a.distance-b.distance)
  const nearest = choices.filter(c => Math.abs(c.distance-choices[0].distance)<1e-6)
  return nearest.filter((c,i) => !nearest.slice(0,i).some(p => c.kind === 'junction' && p.kind === 'junction'
    && c.wireId === p.wireId && Math.hypot(c.point.x-p.point.x,c.point.y-p.point.y)<1e-8))
}
