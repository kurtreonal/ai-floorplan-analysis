// A wall magnet changes the canonical anchor so 2D, 3D and takeoff agree.
export function deviceWallSnap(point, symbol, draft, presentation, threshold) {
  if (!['outlet', 'switch', 'panel', 'pull-station', 'alarm'].includes(presentation?.family)) return null
  let best = null
  for (const wall of draft.walls || []) {
    if (wall.disposition === 'rejected') continue
    const dx = wall.end.x - wall.start.x, dy = wall.end.y - wall.start.y, square = dx * dx + dy * dy
    if (!square) continue
    const t = Math.max(0, Math.min(1, ((point.x - wall.start.x) * dx + (point.y - wall.start.y) * dy) / square))
    const target = { x: wall.start.x + t * dx, y: wall.start.y + t * dy }
    const distance = Math.hypot(point.x - target.x, point.y - target.y)
    if (distance <= threshold && (!best || distance < best.distance)) best = { point: target, wallId: wall.id, distance, kind: 'wall' }
  }
  return best
}
