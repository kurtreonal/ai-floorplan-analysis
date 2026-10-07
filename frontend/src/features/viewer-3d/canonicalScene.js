import { normalizeCanonicalGeometry } from '../../geometry/canonicalGeometry.js'
import { normalizeCanonicalExtension } from '../../geometry/canonicalExtension.js'

export function canonicalPointToWorld(point, elevation) {
  if (![point.x, point.y, elevation].every(Number.isFinite)) throw new Error('Invalid metric position.')
  return [point.x, elevation, point.y]
}

// ShapeGeometry is in XY; rotating -PI/2 maps its negative Y to world +Z.
export function canonicalRoomShapePoints(boundary) {
  return boundary.map((point) => [point.x, -point.y])
}

export function buildCanonicalScene(document, extension = null) {
  const geometry = normalizeCanonicalGeometry(document)
  const details = extension ? normalizeCanonicalExtension(extension, geometry).route_details : []
  const routeDetails = new Map(details.map((detail) => [detail.route_id, detail]))
  const elevation = geometry.floor.elevation_meters
  const width = geometry.coordinate_system.width_meters
  const depth = geometry.coordinate_system.height_meters
  const renderableWalls = geometry.walls.filter((wall) => wall.status === 'verified' && wall.length_meters > 0)
  const missing = renderableWalls.filter((wall) => wall.height_meters === null || wall.thickness_meters === null)
  if (missing.length) throw new Error('Approve wall height and thickness before opening metric 3D.')
  const walls = renderableWalls.map((wall) => ({
    id: wall.id,
    position: [(wall.start.x + wall.end.x) / 2, elevation + wall.height_meters / 2, (wall.start.y + wall.end.y) / 2],
    size: [wall.length_meters, wall.height_meters, wall.thickness_meters],
    rotation: [0, -Math.atan2(wall.end.y - wall.start.y, wall.end.x - wall.start.x), 0],
  }))
  let omittedRouteSegmentCount = 0
  const routeSegments = geometry.routes.flatMap((route) => route.points.slice(1).flatMap((end, index) => {
    const start = route.points[index]
    // Other floors have no approved transform in a single-floor snapshot.
    if (start.project_floor_id !== geometry.floor.project_floor_id || end.project_floor_id !== geometry.floor.project_floor_id) {
      omittedRouteSegmentCount += 1
      return []
    }
    return [{
      routeId: route.id, segmentIndex: index,
      provenance: routeDetails.get(route.id)?.route_kind ?? 'unresolved',
      installationMethod: 'unresolved', elevationState: 'stored',
      start: canonicalPointToWorld(start, start.elevation_meters),
      end: canonicalPointToWorld(end, end.elevation_meters),
    }]
  }))
  return {
    width, depth, elevation,
    target: [width / 2, elevation, depth / 2],
    extent: Math.max(width, depth, ...walls.map((wall) => wall.size[1]), 1),
    walls,
    routeSegments, omittedRouteSegmentCount,
    omittedWallCount: geometry.walls.length - walls.length,
    rooms: geometry.rooms.map((room) => ({ id: room.id, boundary: room.boundary })),
    symbols: geometry.symbols.map((symbol) => ({
      id: symbol.id, classification: symbol.class, status: symbol.status,
      position: canonicalPointToWorld(symbol.position, elevation),
    })),
  }
}
