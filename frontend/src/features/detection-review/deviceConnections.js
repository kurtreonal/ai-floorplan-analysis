// Device terminal bindings and committed shared-node edits. Crossings alone
// never imply connectivity; path magnets commit through the junction model.
import { moveDraftWirePoint } from './draftWiringScene.js'
import { joinWireJunction, moveJunctionVertex } from './wireJunctions.js'

// Source-coordinate contact test, independent of camera, zoom or pixel density.
// Only endpoints meeting a device port qualify; segment crossings never do.
export function connectTouchingWireEndpoints(draft, presentations = {}) {
  let changed = false
  const wirings = (draft.wirings || []).map(w => ({...w, points:w.points.map(p => ({...p})),
    device_attachments:[...(w.device_attachments || [])]}))
  for (const wire of wirings) {
    if (wire.disposition === 'rejected' || wire.suppression_reason || wire.source_evidence_required || wire.assignment_state === 'unresolved') continue
    for (const index of [0,wire.points.length-1]) {
      if (wire.device_attachments.some(a => a.point_index === index)
        || wire.junction_attachments?.some(a => a.point_index === index)
        || wire.auto_connect_disabled_endpoints?.includes(index)) continue
      const point = wire.points[index], neighbor = wire.points[index === 0 ? 1 : index-1]
      const length = Math.hypot(point.x-neighbor.x,point.y-neighbor.y)
      if (!length) continue
      const choices = []
      for (const symbol of draft.symbols || []) {
        if (symbol.disposition === 'rejected' || presentations[symbol.id]?.family === 'annotation'
          || !symbol.center || wire.device_attachments.some(a => a.symbol_id === symbol.id)
          || (symbol.center.x === neighbor.x && symbol.center.y === neighbor.y)) continue
        const circuit = wire.circuit_id || wire.circuit_ref
        if (circuit && wirings.some(other => other.disposition !== 'rejected' && !other.suppression_reason && (other.circuit_id || other.circuit_ref)
          && (other.circuit_id || other.circuit_ref) !== circuit && other.device_attachments.some(a => a.symbol_id === symbol.id))) continue
        const bounds = presentations[symbol.id]?.sourceBounds
        const distance = Math.hypot(point.x-symbol.center.x,point.y-symbol.center.y)
        if (bounds) {
          if (point.x < bounds.x-2 || point.x > bounds.x+bounds.width+2
            || point.y < bounds.y-2 || point.y > bounds.y+bounds.height+2) continue
          const perpendicular = Math.abs((symbol.center.x-point.x)*(neighbor.y-point.y)
            -(symbol.center.y-point.y)*(neighbor.x-point.x))/length
          if (perpendicular > Math.max(2,Math.min(8,Math.min(bounds.width,bounds.height)*.3))) continue
        } else if (distance > 2) continue
        choices.push({distance,symbol})
      }
      choices.sort((a,b) => a.distance-b.distance || a.symbol.id.localeCompare(b.symbol.id))
      if (!choices.length || (choices[1] && Math.abs(choices[0].distance-choices[1].distance)<1)) continue
      const symbol = choices[0].symbol
      wire.points[index] = {...symbol.center}
      wire.device_attachments.push({symbol_id:symbol.id,point_index:index})
      changed = true
    }
  }
  return changed ? {...draft,wirings} : draft
}

export function findWireDeviceSnap(point, wireId, pointIndex, draft, presentations = {}, threshold = 14, distanceToSymbol = null) {
  if (!point || ![point.x, point.y].every(Number.isFinite)) return null
  const wire = (draft.wirings || []).find(w => w.id === wireId && w.disposition !== 'rejected')
  if (!wire || ![0, wire.points.length - 1].includes(pointIndex) || !Number.isFinite(threshold) || threshold < 0) return null
  if (wire.junction_attachments?.some(a => a.point_index === pointIndex)) return null
  const candidates = []
  for (const symbol of draft.symbols || []) {
    if (symbol.disposition === 'rejected' || presentations[symbol.id]?.family === 'annotation'
      || !symbol.center || ![symbol.center.x, symbol.center.y].every(Number.isFinite)) continue
    // Do not bridge unrelated runs or close a loop through the same device.
    const circuit = wire.circuit_id || wire.circuit_ref
    if ((draft.wirings || []).some(w => w.disposition !== 'rejected' && (w.device_attachments || []).some(a =>
      a.symbol_id === symbol.id && (w.id === wireId ? a.point_index !== pointIndex
        : circuit && (w.circuit_id || w.circuit_ref) && (w.circuit_id || w.circuit_ref) !== circuit)))) continue
    const neighbor = wire.points[pointIndex === 0 ? 1 : pointIndex - 1]
    if (neighbor.x === symbol.center.x && neighbor.y === symbol.center.y) continue
    const distance = distanceToSymbol ? distanceToSymbol(symbol) : Math.hypot(point.x - symbol.center.x, point.y - symbol.center.y)
    if (Number.isFinite(distance) && distance <= threshold) candidates.push({ symbolId: symbol.id, point: {...symbol.center}, distance })
  }
  candidates.sort((a,b) => a.distance - b.distance || a.symbolId.localeCompare(b.symbolId))
  if (!candidates.length || (candidates[1] && Math.abs(candidates[0].distance - candidates[1].distance) < 1e-6)) return null
  return candidates[0]
}

export function moveConnectedWirePoint(draft, wireId, pointIndex, point, width, height, snap = null, presentations = {}) {
  const wire = (draft.wirings || []).find(w => w.id === wireId && w.disposition !== 'rejected')
  if (!wire) return draft
  if (snap?.kind === 'junction') {
    if (![0,wire.points.length-1].includes(pointIndex)) return draft
    return joinWireJunction(draft,wireId,pointIndex,snap.wireId,snap.segmentIndex,snap.t)
  }
  if (wire.junction_attachments?.some(a => a.point_index === pointIndex)) {
    if (snap) return draft // Detach the junction before binding a device terminal.
    const updated = moveDraftWirePoint(wire, pointIndex, point, width, height)
    return updated ? moveJunctionVertex(draft, wireId, pointIndex, updated.points[pointIndex]) : draft
  }
  let updated
  if (snap) {
    // Revalidate against current shared state on commit, not a stale UI preview.
    const valid = findWireDeviceSnap(snap.point, wireId, pointIndex, draft, presentations, 0)
    if (!valid || valid.symbolId !== snap.symbolId || valid.point.x < 0 || valid.point.x > width
      || valid.point.y < 0 || valid.point.y > height) return draft
    updated = {...wire, points: wire.points.map((p,i) => i === pointIndex ? valid.point : p),
      disposition: wire.disposition === 'added' ? 'added' : 'corrected',
      ...(wire.origin === 'generated' ? {suppression_reason:null} : {})}
  } else {
    updated = moveDraftWirePoint(wire, pointIndex, point, width, height)
    if (!updated) return draft
  }
  updated.device_attachments = [...(wire.device_attachments || []).filter(a => a.point_index !== pointIndex),
    ...(snap ? [{symbol_id: snap.symbolId, point_index: pointIndex}] : [])]
  updated.auto_connect_disabled_endpoints = [...new Set([
    ...(wire.auto_connect_disabled_endpoints || []).filter(i => i !== pointIndex),
    ...(!snap && wire.device_attachments?.some(a => a.point_index === pointIndex) ? [pointIndex] : []),
  ])]
  return {...draft, wirings: draft.wirings.map(w => w.id === wireId ? updated : w)}
}

export function findDeviceWireSnap(point, symbolId, wires, threshold) {
  const candidates = []
  const connected = (wires || []).filter(w => w.disposition !== 'rejected' &&
    (w.device_attachments || []).some(a => a.symbol_id === symbolId))
  for (const wire of wires || []) {
    if (wire.disposition === 'rejected') continue
    // Detach first before choosing an unrelated run; never silently bridge
    // independent circuits through a moved device.
    if (connected.some(w => w.id !== wire.id)) continue
    for (const index of [0, wire.points.length - 1]) {
      if (wire.junction_attachments?.some(a => a.point_index === index)) continue
      if ((wire.device_attachments || []).some(a => a.symbol_id === symbolId && a.point_index !== index)) continue
      if ((wire.device_attachments || []).some(a => a.point_index === index && a.symbol_id !== symbolId)) continue
      const p = wire.points[index]
      const distance = Math.hypot(point.x - p.x, point.y - p.y)
      if (distance <= threshold) candidates.push({ wireId: wire.id, pointIndex: index, point: {...p}, distance })
    }
  }
  candidates.sort((a,b) => a.distance - b.distance || a.wireId.localeCompare(b.wireId))
  // Equidistant independent wires are ambiguous, not a guessed junction.
  if (!candidates.length || (candidates[1] && Math.abs(candidates[0].distance-candidates[1].distance) < 1e-6)) return null
  return candidates[0]
}

export function moveConnectedDevice(draft, symbol, snap = null) {
  const current = draft.symbols.find(s => s.id === symbol.id)
  if (!current) return draft
  if (snap && (draft.wirings || []).some(w => w.disposition !== 'rejected' && w.id !== snap.wireId &&
    (w.device_attachments || []).some(a => a.symbol_id === symbol.id))) return draft
  const center = snap?.point ?? symbol.center
  const wirings = (draft.wirings || []).map(wire => {
    if (wire.disposition === 'rejected') return wire
    let attachments = wire.device_attachments || []
    if (snap?.wireId === wire.id) attachments = [...attachments.filter(a => a.point_index !== snap.pointIndex),
      {symbol_id: symbol.id, point_index: snap.pointIndex}]
    const indices = new Set(attachments.filter(a => a.symbol_id === symbol.id).map(a => a.point_index))
    if (!indices.size) return wire
    return {...wire, device_attachments: attachments,
      points: wire.points.map((p,i) => indices.has(i) ? {...center} : p),
      disposition: wire.disposition === 'added' ? 'added' : 'corrected'}
  })
  if (wirings.some((w, index) => w !== draft.wirings[index] && w.disposition !== 'rejected' && w.points.some((p,i) =>
    i > 0 && p.x === w.points[i-1].x && p.y === w.points[i-1].y))) return draft
  return {...draft, wirings, symbols: draft.symbols.map(s => s.id === symbol.id ? {...symbol, center,
    disposition: s.disposition === 'added' ? 'added' : 'corrected'} : s)}
}

export function detachDevice(draft, symbolId) {
  return {...draft, wirings: (draft.wirings || []).map(w => ({...w,
    auto_connect_disabled_endpoints: [...new Set([...(w.auto_connect_disabled_endpoints || []),
      ...(w.device_attachments || []).filter(a => a.symbol_id === symbolId).map(a => a.point_index)])],
    device_attachments: (w.device_attachments || []).filter(a => a.symbol_id !== symbolId)}))}
}
