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

export function findWireDeviceSnap(point, wireId, pointIndex, draft, presentations = {}, threshold = 14, distanceToSymbol = null, targetSymbolId = null) {
  const candidates = findWireDeviceTargets(point, wireId, pointIndex, draft, presentations, threshold, distanceToSymbol, targetSymbolId)
  if (!candidates.length || (candidates[1] && Math.abs(candidates[0].distance - candidates[1].distance) < 1e-6)) return null
  // Preserve the legacy symbol-only shape for old inspector callers.
  const { terminalId, ...candidate } = candidates[0]
  return terminalId === 'design-anchor' ? candidate : candidates[0]
}

export function findWireDeviceTargets(point, wireId, pointIndex, draft, presentations = {}, threshold = 14, distanceToSymbol = null, targetSymbolId = null) {
  if (!point || ![point.x, point.y].every(Number.isFinite)) return []
  const wire = (draft.wirings || []).find(w => w.id === wireId && w.disposition !== 'rejected')
  if (!wire || ![0, wire.points.length - 1].includes(pointIndex) || !Number.isFinite(threshold) || threshold < 0) return []
  if (wire.junction_attachments?.some(a => a.point_index === pointIndex)) return []
  const candidates = []
  for (const symbol of draft.symbols || []) {
    // An explicit inspector choice disambiguates co-located devices by stable ID.
    // Automatic magnets still reject equally close ports and never pick one by ID.
    if (targetSymbolId && symbol.id !== targetSymbolId) continue
    if (symbol.disposition === 'rejected' || presentations[symbol.id]?.family === 'annotation'
      || !symbol.center || ![symbol.center.x, symbol.center.y].every(Number.isFinite)) continue
    // Do not bridge unrelated runs or close a loop through the same device.
    const circuit = wire.circuit_id || wire.circuit_ref
    if ((draft.wirings || []).some(w => w.disposition !== 'rejected' && (w.device_attachments || []).some(a =>
      a.symbol_id === symbol.id && (w.id === wireId ? a.point_index !== pointIndex
        : circuit && (w.circuit_id || w.circuit_ref) && (w.circuit_id || w.circuit_ref) !== circuit)))) continue
    const neighbor = wire.points[pointIndex === 0 ? 1 : pointIndex - 1]
    if (neighbor.x === symbol.center.x && neighbor.y === symbol.center.y) continue
    // Existing explicit terminals are real identities, not one merged device port.
    // Unspecified legacy bindings do not manufacture electrical pins.
    const terminals = new Map()
    for (const other of draft.wirings || []) {
      if (other.disposition === 'rejected' || other.suppression_reason) continue
      for (const attachment of other.device_attachments || []) {
        if (attachment.symbol_id !== symbol.id || !attachment.terminal_id) continue
        const anchor = other.points[attachment.point_index]
        if (!anchor || ![anchor.x,anchor.y].every(Number.isFinite)) continue
        const previous = terminals.get(attachment.terminal_id)
        // The current review contract stores terminals at the canonical device
        // anchor. Unsupported offsets stay unresolved, not an unsaveable snap.
        terminals.set(attachment.terminal_id, previous === null || anchor.x !== symbol.center.x || anchor.y !== symbol.center.y
          || (previous && (previous.x !== anchor.x || previous.y !== anchor.y)) ? null : anchor)
      }
    }
    if (!terminals.size) terminals.set('design-anchor', symbol.center)
    for (const [terminalId, anchor] of terminals) {
      if (!anchor || (neighbor.x === anchor.x && neighbor.y === anchor.y)) continue
      const distance = distanceToSymbol ? distanceToSymbol({...symbol,center:anchor,terminalId}) : Math.hypot(point.x-anchor.x,point.y-anchor.y)
      if (Number.isFinite(distance) && distance <= threshold) candidates.push({symbolId:symbol.id,terminalId,point:{...anchor},distance})
    }
  }
  return candidates.sort((a,b) => a.distance-b.distance || a.symbolId.localeCompare(b.symbolId) || a.terminalId.localeCompare(b.terminalId))
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
    const valid = snap.terminalId
      ? findWireDeviceTargets(snap.point, wireId, pointIndex, draft, presentations, 0, null, snap.symbolId).find(c => c.terminalId === snap.terminalId)
      : findWireDeviceSnap(snap.point, wireId, pointIndex, draft, presentations, 0, null, snap.symbolId)
    if (!valid || valid.symbolId !== snap.symbolId || valid.point.x < 0 || valid.point.x > width
      || valid.point.y < 0 || valid.point.y > height) return draft
    updated = {...wire, points: wire.points.map((p,i) => i === pointIndex ? valid.point : p),
      disposition: wire.disposition === 'added' ? 'added' : 'corrected',
      ...(wire.origin === 'generated' ? {suppression_reason:null} : {})}
  } else {
    updated = moveDraftWirePoint(wire, pointIndex, point, width, height)
    if (!updated) return draft
  }
  if (wire.vertex_ids) {
    const identity=wire.vertex_ids[pointIndex]
    updated={...updated,points:updated.points.map((p,i)=>wire.vertex_ids[i]===identity?{...updated.points[pointIndex]}:p)}
    if(updated.points.some((p,i)=>i>0&&p.x===updated.points[i-1].x&&p.y===updated.points[i-1].y))return draft
  }
  updated.device_attachments = [...(wire.device_attachments || []).filter(a => a.point_index !== pointIndex),
    ...(snap ? [{symbol_id: snap.symbolId, point_index: pointIndex, ...(snap.terminalId ? {terminal_id:snap.terminalId} : {})}] : [])]
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
    const identities=new Set([...indices].map(i=>wire.vertex_ids?.[i]).filter(Boolean))
    wire.vertex_ids?.forEach((id,i)=>{if(identities.has(id))indices.add(i)})
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
