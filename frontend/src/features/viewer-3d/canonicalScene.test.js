import { describe, expect, it } from 'vitest'
import fixture from '../../../../fixtures/canonical_geometry_v1.json'
import { buildCanonicalScene, canonicalPointToWorld } from './canonicalScene.js'
import { canonicalRoomShapePoints } from './canonicalScene.js'
import { Vector3 } from 'three'

function reviewed() {
  const geometry = structuredClone(fixture)
  Object.assign(geometry.walls[0], { status: 'verified', height_meters: 3, thickness_meters: 0.15 })
  return geometry
}

describe('canonical scene coordinates', () => {
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
    expect(buildCanonicalScene(geometry).symbols).toEqual([{ id: 'detected:501', position: [1, -1.5, 2] }])
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
