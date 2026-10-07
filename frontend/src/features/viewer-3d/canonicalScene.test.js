import { describe, expect, it } from 'vitest'
import fixture from '../../../../fixtures/canonical_geometry_v1.json'
import { buildCanonicalScene, canonicalPointToWorld } from './canonicalScene.js'
import { canonicalRoomShapePoints } from './canonicalScene.js'
import { Vector3 } from 'three'
import { CanonicalScene } from './CanonicalScene.jsx'

function reviewed() {
  const geometry = structuredClone(fixture)
  Object.assign(geometry.walls[0], { status: 'verified', height_meters: 3, thickness_meters: 0.15 })
  return geometry
}

function wiringGeometry() {
  const geometry = reviewed()
  geometry.routes = [{ id: 41, points: [
    { project_floor_id: 2, x: 1, y: 1, elevation_meters: -2 },
    { project_floor_id: 2, x: 3, y: 2, elevation_meters: 0.75 },
  ] }]
  return geometry
}

function routeExtension(geometry, kind) {
  return { extension_schema_version: 2, base_schema_version: 1,
    source_plane_reference: { floor_plan_page_id: 1, source_artifact_id: 2,
      width_pixels: geometry.coordinate_system.image_width_pixels,
      height_pixels: geometry.coordinate_system.image_height_pixels },
    openings: [], panels: [], symbol_details: [],
    route_details: [{ route_id: 41, route_kind: kind, provenance_ref: null }] }
}

function elements(node) {
  if (Array.isArray(node)) return node.flatMap(elements)
  if (!node || typeof node !== 'object' || !node.props) return []
  return [node, ...elements(node.props.children)]
}

describe('canonical scene coordinates', () => {
  it('renders saved route elevations without assuming observed provenance or installation method', () => {
    const geometry = wiringGeometry()
    const before = JSON.stringify(geometry)
    const scene = buildCanonicalScene(geometry)
    expect(scene.routeSegments).toEqual([{ routeId: 41, segmentIndex: 0,
      provenance: 'unresolved', installationMethod: 'unresolved', elevationState: 'stored',
      start: [1, -2, 1], end: [3, 0.75, 2] }])
    expect(JSON.stringify(geometry)).toBe(before)
    const rendered = elements(CanonicalScene({ scene }))
    const line = rendered.find((element) => element.type === 'line')
    expect(line.props.userData).toMatchObject({ provenance: 'unresolved', elevationState: 'stored' })
    expect(Array.from(rendered.find((element) => element.type === 'bufferAttribute').props.args[0]))
      .toEqual([1, -2, 1, 3, 0.75, 2])
  })
  it.each(['observed', 'generated'])('uses only validated extension metadata for %s provenance', (kind) => {
    const geometry = wiringGeometry()
    const scene = buildCanonicalScene(geometry, routeExtension(geometry, kind))
    expect(scene.routeSegments[0]).toMatchObject({ provenance: kind, installationMethod: 'unresolved' })
    const material = elements(CanonicalScene({ scene })).find((element) => element.type === 'lineBasicMaterial')
    expect(material.props.color).toBe(kind === 'observed' ? '#8a5a00' : '#64748b')
    const invalid = routeExtension(geometry, kind)
    invalid.route_details[0].route_id = 99
    expect(() => buildCanonicalScene(geometry, invalid)).toThrow(/canonical geometry/)
  })
  it('omits cross-floor edges without bridging the remaining points or inventing offsets', () => {
    const geometry = wiringGeometry()
    const [start, end] = geometry.routes[0].points
    geometry.routes[0].points = [start, { ...end, project_floor_id: 3 }, start, end]
    const scene = buildCanonicalScene(geometry)
    expect(scene.omittedRouteSegmentCount).toBe(2)
    expect(scene.routeSegments).toHaveLength(1)
    expect(scene.routeSegments[0]).toMatchObject({ segmentIndex: 2, start: [1, -2, 1], end: [3, 0.75, 2] })
  })
  it('rejects invalid saved elevations and supports older scenes without route segments', () => {
    const geometry = wiringGeometry()
    geometry.routes[0].points[0].elevation_meters = NaN
    expect(() => buildCanonicalScene(geometry)).toThrow(/canonical geometry/)
    const scene = buildCanonicalScene(reviewed())
    delete scene.routeSegments
    expect(elements(CanonicalScene({ scene })).filter((element) => element.type === 'line')).toEqual([])
  })
  it('derives the floor extent from scale, including an empty layout', () => {
    const geometry = reviewed()
    Object.assign(geometry.coordinate_system, { pixels_per_meter: 50, width_meters: 12.8, height_meters: 9.6 })
    Object.assign(geometry, { walls: [], rooms: [], symbols: [], routes: [] })
    expect(buildCanonicalScene(geometry)).toMatchObject({ width: 12.8, depth: 9.6, elevation: -1.5, target: [6.4, -1.5, 4.8] })
  })
  it('projects an asymmetric room without mirroring the 2D boundary', () => {
    const boundary = [{ x: 1, y: 2 }, { x: 4, y: 2 }, { x: 2, y: 3 }]
    canonicalRoomShapePoints(boundary).forEach(([x, y], index) => {
      const point = new Vector3(x, y, 0).applyAxisAngle(new Vector3(1, 0, 0), -Math.PI / 2)
      expect(point.x).toBeCloseTo(boundary[index].x)
      expect(point.z).toBeCloseTo(boundary[index].y)
      expect(point.y).toBeCloseTo(0)
    })
  })
  it('preserves meters, image-down direction and negative floor elevation', () => {
    const scene = buildCanonicalScene(reviewed())
    expect(scene.symbols[0].position).toEqual([2.5, -1.5, 1.5])
    expect(scene.walls[0].position).toEqual([1.2000000000000002, 0, 0.35])
    expect(scene.walls[0].size).toEqual([2, 3, 0.15])
    expect(scene.rooms[0].boundary).toEqual(fixture.rooms[0].boundary)
  })
  it('maps a vertical and a rotated wall from endpoints', () => {
    const geometry = reviewed()
    Object.assign(geometry.walls[0], { start: { x: 1, y: 1 }, end: { x: 1, y: 3 }, length_meters: 2, angle_degrees: 90 })
    expect(buildCanonicalScene(geometry).walls[0].rotation[1]).toBeCloseTo(-Math.PI / 2)
    Object.assign(geometry.walls[0], { end: { x: 3, y: 3 }, length_meters: Math.sqrt(8), angle_degrees: 45 })
    expect(buildCanonicalScene(geometry).walls[0].rotation[1]).toBeCloseTo(-Math.PI / 4)
  })
  it('uses changed saved positions and excludes removed symbols without mutating input', () => {
    const geometry = reviewed()
    geometry.symbols[0].position = { x: 1, y: 2 }
    geometry.symbols.pop()
    const before = JSON.stringify(geometry)
    expect(buildCanonicalScene(geometry).symbols).toEqual([expect.objectContaining({ id: 'detected:501', position: [1, -1.5, 2] })])
    expect(JSON.stringify(geometry)).toBe(before)
  })
  it('blocks missing wall dimensions and invalid coordinates', () => {
    const geometry = reviewed()
    geometry.walls[0].height_meters = null
    expect(() => buildCanonicalScene(geometry)).toThrow(/Approve wall height/)
    expect(() => canonicalPointToWorld({ x: NaN, y: 1 }, 0)).toThrow()
  })
  it('omits unreviewed walls without blocking the stored floor', () => {
    expect(buildCanonicalScene(fixture)).toMatchObject({ width: 6.4, walls: [], omittedWallCount: 1 })
  })
  it('retains confirmed and manual symbol identities and approved class names', () => {
    const scene = buildCanonicalScene(reviewed())
    expect(scene.symbols).toEqual([
      { id: 'detected:501', classification: { id: 7, name: 'Power outlet' }, status: 'confirmed', position: [2.5, -1.5, 1.5] },
      { id: 'manual:601', classification: { id: 2, name: 'Wall light' }, status: 'manually_added', position: [4.1, -1.5, 2.25] },
    ])
  })
  it.each(['deleted', 'rejected', 'detected', 'needs_review'])('rejects a noncanonical %s symbol instead of displaying it', (status) => {
    const geometry = reviewed()
    geometry.symbols[0].status = status
    expect(() => buildCanonicalScene(geometry)).toThrow(/canonical geometry/)
  })
  it('omits a verified zero-length wall without inventing dimensions', () => {
    const geometry = reviewed()
    Object.assign(geometry.walls[0], { end: { ...geometry.walls[0].start }, length_meters: 0, height_meters: null })
    expect(buildCanonicalScene(geometry).walls).toEqual([])
  })
  it.each([
    [{ x: 1, y: 1 }, { x: 4, y: 1 }],
    [{ x: 1, y: 1 }, { x: 1, y: 4 }],
    [{ x: 4, y: 3 }, { x: 1, y: 1 }],
  ])('places both extruded endpoints at canonical coordinates: %j → %j', (start, end) => {
    const geometry = reviewed()
    Object.assign(geometry.walls[0], { start, end, length_meters: Math.hypot(end.x - start.x, end.y - start.y), height_meters: 2.4, thickness_meters: 0.22 })
    const wall = buildCanonicalScene(geometry).walls[0]
    ;[start, end].forEach((point, index) => {
      const world = new Vector3((index ? 1 : -1) * wall.size[0] / 2, -wall.size[1] / 2, 0)
        .applyAxisAngle(new Vector3(0, 1, 0), wall.rotation[1]).add(new Vector3(...wall.position))
      expect(world.x).toBeCloseTo(point.x)
      expect(world.z).toBeCloseTo(point.y)
      expect(world.y).toBeCloseTo(geometry.floor.elevation_meters)
    })
    expect(wall.size.slice(1)).toEqual([2.4, 0.22])
  })
})
