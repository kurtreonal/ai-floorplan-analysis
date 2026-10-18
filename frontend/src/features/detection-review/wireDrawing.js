// Draft installation intent only; no depth, conductor count or circuit approval.
export function withWiringMethod(wire, method) {
  if (!['concealed_in_ceiling','concealed_under_floor'].includes(method)) return wire
  return { ...wire, installation_method: method,
    line_style: method === 'concealed_under_floor' ? 'dashed' : 'solid',
    wiring_legend_id: null, wiring_legend_name: null }
}

export function snapWiringPoint(point, draft, presentations = {}, threshold = 12) {
  const candidates = []
  for (const symbol of (draft.symbols || []).slice(0,2048)) {
    if (symbol.disposition === 'rejected' || presentations[symbol.id]?.family === 'annotation') continue
    candidates.push({ ...symbol.center, kind: 'device', id: symbol.id, priority: 0 })
  }
  let examined = 0
  for (const wire of draft.wirings || []) {
    if (wire.disposition === 'rejected') continue
    for (let i = 1; i < wire.points.length && examined < 512; i++, examined++) {
      const a = wire.points[i-1], b = wire.points[i], dx = b.x-a.x, dy = b.y-a.y
      candidates.push({ ...a, kind: 'wire', id: wire.id, priority: 1 }, { ...b, kind: 'wire', id: wire.id, priority: 1 })
      const length = dx*dx+dy*dy
      if (!length) continue
      const t = Math.max(0,Math.min(1,((point.x-a.x)*dx+(point.y-a.y)*dy)/length))
      candidates.push({ x: a.x+t*dx, y: a.y+t*dy, kind: 'wire', id: wire.id, priority: 2 })
    }
    if (examined >= 512) break
  }
  const ordered = candidates.map(p => ({ ...p, distance: Math.hypot(p.x-point.x,p.y-point.y) }))
    .filter(p => Number.isFinite(p.distance) && p.distance <= threshold)
    .sort((a,b) => a.priority-b.priority || a.distance-b.distance)
  const nearest = ordered[0]
  if (nearest && ordered.some(p => p!==nearest && p.priority===nearest.priority && Math.abs(p.distance-nearest.distance)<1e-6 && (p.id!==nearest.id || p.kind!==nearest.kind))) return {...point,snapped:false}
  return nearest ? { x: nearest.x, y: nearest.y, snapped: true, kind: nearest.kind, id: nearest.id }
    : { ...point, snapped: false }
}
