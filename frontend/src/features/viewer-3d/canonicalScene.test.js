import { describe, expect, it } from 'vitest'
import fixture from '../../../../fixtures/canonical_geometry_v1.json'
import { buildCanonicalScene, canonicalPointToWorld } from './canonicalScene.js'

function reviewed() {
  const geometry = structuredClone(fixture)
  Object.assign(geometry.walls[0], { status: 'verified', height_meters: 3, thickness_meters: 0.15 })
  return geometry
}

describe('canonical scene coordinates', () => {
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
    expect(() => buildCanonicalScene(fixture)).toThrow(/Approve wall height/)
    expect(() => canonicalPointToWorld({ x: NaN, y: 1 }, 0)).toThrow()
  })
})
