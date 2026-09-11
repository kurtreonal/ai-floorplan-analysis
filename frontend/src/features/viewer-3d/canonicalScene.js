import { normalizeCanonicalGeometry } from '../../geometry/canonicalGeometry.js'

export function canonicalPointToWorld(point, elevation) {
  if (![point.x, point.y, elevation].every(Number.isFinite)) throw new Error('Invalid metric position.')
  return [point.x, elevation, point.y]
}

export function buildCanonicalScene(document) {
  const geometry = normalizeCanonicalGeometry(document)
  const elevation = geometry.floor.elevation_meters
  const width = geometry.coordinate_system.width_meters
  const depth = geometry.coordinate_system.height_meters
  const missing = geometry.walls.filter((wall) => wall.height_meters === null || wall.thickness_meters === null)
  if (missing.length) throw new Error('Approve wall height and thickness before opening metric 3D.')
  const walls = geometry.walls.filter((wall) => wall.status === 'verified' && wall.length_meters > 0).map((wall) => ({
    id: wall.id,
    position: [(wall.start.x + wall.end.x) / 2, elevation + wall.height_meters / 2, (wall.start.y + wall.end.y) / 2],
    size: [wall.length_meters, wall.height_meters, wall.thickness_meters],
    rotation: [0, -Math.atan2(wall.end.y - wall.start.y, wall.end.x - wall.start.x), 0],
  }))
  return {
    width, depth, elevation,
    target: [width / 2, elevation, depth / 2],
    extent: Math.max(width, depth, ...walls.map((wall) => wall.size[1]), 1),
    walls,
    rooms: geometry.rooms.map((room) => ({ id: room.id, boundary: room.boundary })),
    symbols: geometry.symbols.map((symbol) => ({ id: symbol.id, position: canonicalPointToWorld(symbol.position, elevation) })),
  }
}
