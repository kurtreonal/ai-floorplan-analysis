// Advisory display adapter only. Both views use the same source-pixel room draft.
// Its relative units and boundary extrusions must never enter canonical saves.
import { draftWiringScene } from './draftWiringScene.js'
import {sceneWallTopology} from '../../geometry/wallTopology.js'
import {withMountingDefaults} from './deviceMounting.js'
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

export function buildDraftRoomScene(draft, width, height, relativeHeight = 0.8, presentations = {}, preview = {}) {
  if (![width, height, relativeHeight].every(Number.isFinite) || width <= 0 || height <= 0 || relativeHeight < 0 || relativeHeight > 12) {
    throw new Error('Invalid preview dimensions.')
  }
  const scale = 10 / Math.max(width, height)
  const measured=Number.isFinite(preview.pixelsPerMeter)&&preview.pixelsPerMeter>0
  const longSideMeters = measured ? Math.max(width,height)/preview.pixelsPerMeter : preview.longSideMeters ?? 40
  if (!Number.isFinite(longSideMeters) || longSideMeters <= 0 || !measured&&(longSideMeters < 5 || longSideMeters > 500)) throw new Error('Preview plan length must be between 5 and 500 m.')
  const unitsPerMeter = 10 / longSideMeters
  const wallThickness = (preview.wallThicknessMeters ?? 0.18) * unitsPerMeter
  if (!Number.isFinite(wallThickness) || wallThickness <= 0) throw new Error('Invalid preview wall thickness.')
  const rooms = draft.rooms.filter((room) => room.disposition !== 'rejected').map((room) => {
    if (room.boundary.length < 3 || room.boundary.length > 512 || room.boundary.some(({ x, y }) => !Number.isFinite(x) || !Number.isFinite(y) || x < 0 || y < 0 || x > width || y > height)) {
      throw new Error('A room boundary is outside the image. Correct its points in 2D first.')
    }
    if (!isSimpleBoundary(room.boundary)) throw new Error('A room boundary crosses itself or has no area. Correct its corners in 2D first.')
    return { id: room.id, boundary: room.boundary.map(({ x, y }) => ({ x: x * scale, y: y * scale })) }
  })
  const acceptedWalls = (draft.walls || []).filter((wall) => wall.disposition !== 'rejected')
  const wallBoxes = acceptedWalls.length > 0
    ? acceptedWalls.flatMap((wall) => {
      const sx = wall.start.x * scale
      const sy = wall.start.y * scale
      const ex = wall.end.x * scale
      const ey = wall.end.y * scale
      const length = Math.hypot(ex - sx, ey - sy)
      if (!length || !relativeHeight) return []
      const height=Number.isFinite(wall.height_meters)?wall.height_meters*unitsPerMeter:relativeHeight
      const thickness = Number.isFinite(wall.thickness_meters) ? wall.thickness_meters*unitsPerMeter : Number.isFinite(wall.estimated_thickness_pixels) ? wall.estimated_thickness_pixels*scale : wallThickness
      return [{
        id: wall.id,
        position: [(sx + ex) / 2, height / 2, (sy + ey) / 2],
        size: [length, height, thickness],
        rotation: [0, -Math.atan2(ey - sy, ex - sx), 0],
      }]
    })
    : [] // Room boundaries are not detected architectural walls.
  const topology=sceneWallTopology(wallBoxes),walls=topology.walls
  const symbols = (draft.symbols || []).filter((symbol) => symbol.disposition !== 'rejected' && symbol.center
    && [symbol.center.x, symbol.center.y].every(Number.isFinite)
    && symbol.center.x >= 0 && symbol.center.y >= 0 && symbol.center.x <= width && symbol.center.y <= height)
    .map(symbol=>withMountingDefaults(symbol,presentations[symbol.id],preview.mountingDefaults))
    .map((symbol) => ({ id: symbol.id, status: symbol.disposition,
      ...(Number.isFinite(symbol.mounting_height_meters) ? {installation:{provenance:'designer_supplied_planning',
        elevation_meters:symbol.mounting_height_meters+(symbol.terminal_offset_meters??0),wall_id:symbol.mounting_wall_id,
        ...(symbol.mounting_reference || symbol.terminal_offset_meters!=null ? {mounting_reference:symbol.mounting_reference || 'legacy_unspecified',mounting_elevation_meters:symbol.mounting_height_meters}:{}),
        ...(symbol.terminal_offset_meters!=null ? {terminal_offset_meters:symbol.terminal_offset_meters}:{})}} : {}),
      position: [symbol.center.x * scale, 0, symbol.center.y * scale], presentation: presentations[symbol.id] }))
  const scene = { width: width * scale, depth: height * scale, elevation: 0, sourceScale: scale,
    unitsPerMeter, ceilingElevation: relativeHeight, mountingWalls: walls,
    floorElevationMeters: preview.floorElevationMeters,
    serviceHeightAboveFloor:preview.serviceHeightAboveFloor,
    automaticHeights:preview.automaticHeights,
    planningMountingHeights: preview.planningMountingHeights,
    target: [width * scale / 2, 0, height * scale / 2], extent: 10,
    rooms, walls, wallJunctions:topology.junctions, symbols, previewOnly: true, unit: 'relative',
    invalidSymbolCount: (draft.symbols || []).filter((symbol) => symbol.disposition !== 'rejected').length - symbols.length }
  const draftWires = draftWiringScene(draft.wirings, scene)
  return { ...scene, draftWires,
    invalidWiringCount: (draft.wirings || []).filter(wire => wire.disposition !== 'rejected').length - draftWires.length }
}
