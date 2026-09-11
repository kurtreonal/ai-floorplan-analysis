// Advisory display adapter only. Both views use the same source-pixel room draft.
// Its relative units and boundary extrusions must never enter canonical saves.
function isSimpleBoundary(points) {
  const cross = (a, b, c) => (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
  let area = 0
  for (let i = 0; i < points.length; i++) {
    const a = points[i], b = points[(i + 1) % points.length]
    if (a.x === b.x && a.y === b.y) return false
    area += a.x * b.y - b.x * a.y
    for (let j = i + 2; j < points.length; j++) {
      if (i === 0 && j === points.length - 1) continue
      const c = points[j], d = points[(j + 1) % points.length]
      if (Math.max(a.x, b.x) < Math.min(c.x, d.x) || Math.max(c.x, d.x) < Math.min(a.x, b.x) || Math.max(a.y, b.y) < Math.min(c.y, d.y) || Math.max(c.y, d.y) < Math.min(a.y, b.y)) continue
      if (cross(a, b, c) * cross(a, b, d) <= 0 && cross(c, d, a) * cross(c, d, b) <= 0) return false
    }
  }
  return Math.abs(area) > 0.001
}

export function buildDraftRoomScene(draft, width, height, relativeHeight = 0.8) {
  if (![width, height, relativeHeight].every(Number.isFinite) || width <= 0 || height <= 0 || relativeHeight < 0 || relativeHeight > 3) {
    throw new Error('Invalid preview dimensions.')
  }
  const scale = 10 / Math.max(width, height)
  const rooms = draft.rooms.filter((room) => room.disposition !== 'rejected').map((room) => {
    if (room.boundary.length < 3 || room.boundary.length > 512 || room.boundary.some(({ x, y }) => !Number.isFinite(x) || !Number.isFinite(y) || x < 0 || y < 0 || x > width || y > height)) {
      throw new Error('A room boundary is outside the image. Correct its points in 2D first.')
    }
    if (!isSimpleBoundary(room.boundary)) throw new Error('A room boundary crosses itself or has no area. Correct its corners in 2D first.')
    return { id: room.id, boundary: room.boundary.map(({ x, y }) => ({ x: x * scale, y: y * scale })) }
  })
  const walls = rooms.flatMap((room) => room.boundary.flatMap((start, i) => {
    const end = room.boundary[(i + 1) % room.boundary.length]
    const length = Math.hypot(end.x - start.x, end.y - start.y)
    if (!length || !relativeHeight) return []
    return [{ id: `${room.id}-edge-${i}`, position: [(start.x + end.x) / 2, relativeHeight / 2, (start.y + end.y) / 2],
      size: [length, relativeHeight, 0.025], rotation: [0, -Math.atan2(end.y - start.y, end.x - start.x), 0] }]
  }))
  return { width: width * scale, depth: height * scale, elevation: 0,
    target: [width * scale / 2, 0, height * scale / 2], extent: 10,
    rooms, walls, symbols: [], previewOnly: true, unit: 'relative' }
}
