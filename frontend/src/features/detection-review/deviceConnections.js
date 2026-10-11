// Explicit endpoint attachments only. Crossings/interior segment snaps need a
// separately modelled junction and are deliberately not supported here.
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
    device_attachments: (w.device_attachments || []).filter(a => a.symbol_id !== symbolId)}))}
}
