import { normalizeCanonicalGeometry } from '../../geometry/canonicalGeometry.js'
import { normalizeCanonicalExtension } from '../../geometry/canonicalExtension.js'
import { devicePlacement,deviceConnector } from './devicePlacement.js'
import { deviceFamily } from '../detection-review/devicePresentation.js'
import { connectionLead } from './connectionGeometry.js'
import {sceneWallTopology} from '../../geometry/wallTopology.js'

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
  const normalizedExtension = extension ? normalizeCanonicalExtension(extension, geometry) : null
  const details = normalizedExtension?.route_details ?? []
  const installations = new Map((normalizedExtension?.symbol_details ?? []).filter(d => d.installation)
    .map(d => [d.symbol_id, {...d.installation, provenance:'designer_supplied_planning'}]))
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
  const scene = {
    width, depth, elevation,
    target: [width / 2, elevation, depth / 2],
    extent: Math.max(width, depth, ...walls.map((wall) => wall.size[1]), 1),
    walls:sceneWallTopology(walls).walls,
    routeSegments, omittedRouteSegmentCount,
    omittedWallCount: geometry.walls.length - walls.length,
    rooms: geometry.rooms.map((room) => ({ id: room.id, boundary: room.boundary })),
    symbols: geometry.symbols.map((symbol) => ({
      id: symbol.id, classification: symbol.class, status: symbol.status,
      position: canonicalPointToWorld(symbol.position, elevation),
      ...(installations.has(symbol.id) ? {installation:installations.get(symbol.id)} : {}),
    })),
  }
  if (normalizedExtension?.extension_schema_version===4) {
    const contacts = new Map(details.map(d => [d.route_id,d.device_connections]))
    const replacement=[]
    for (const segment of scene.routeSegments) {
      const bindings=contacts.get(segment.routeId) || []
      let projected=false
      for (const contact of bindings) {
        const index=contact.point_index
        const atStart=index===segment.segmentIndex, atEnd=index===segment.segmentIndex+1
        const terminal=atStart ? segment.start : atEnd ? segment.end : null
        // Only the stored mounting-level termination is adjusted. Service
        // contacts remain service contacts; no second drop is inferred here.
        if (!terminal || terminal[1]!==contact.anchor.elevation_meters) continue
        const symbol=scene.symbols.find(s => s.id===contact.symbol_id)
        if (!symbol?.installation) continue
        const connector=deviceConnector(devicePlacement(symbol,scene,deviceFamily(symbol.classification.name)))
        const service=atEnd ? segment.start : segment.end
        const lead=connectionLead(service,connector)
        // A measured canonical vertical branch gets one wall-aligned display
        // rise/drop. Its small housing offset never changes measured geometry.
        if (service[0]===terminal[0] && service[2]===terminal[2] && service[1]!==terminal[1]) {
          replacement.push(...(atEnd ? lead : lead.slice().reverse().map(s => ({...s,start:s.end,end:s.start})))
            .map(s => ({...segment,start:s.start,end:s.end,displayAttachment:true,connectionAnchors:[service,connector]})))
        } else replacement.push({...segment,start:atStart ? connector : segment.start,end:atEnd ? connector : segment.end,connectionAnchors:[connector]})
        projected=true;break
      }
      if (!projected)replacement.push(segment)
    }
    scene.routeSegments=replacement
  }
  return scene
}
