import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { normalizeCanonicalGeometry } from './canonicalGeometry.js'

const fixture = JSON.parse(readFileSync(new URL('../../../fixtures/canonical_geometry_v1.json', import.meta.url), 'utf8'))
const clone = (value) => structuredClone(value)

function changed(path, value) {
  const result = clone(fixture)
  let target = result
  for (const key of path.slice(0, -1)) target = target[key]
  target[path.at(-1)] = value
  return result
}

describe('normalizeCanonicalGeometry', () => {
  it('accepts the shared fixture as a fresh deeply immutable value', () => {
    const normalized = normalizeCanonicalGeometry(fixture)
    expect(normalized).toEqual(fixture)
    expect(normalized).not.toBe(fixture)
    expect(Object.isFrozen(normalized)).toBe(true)
    expect(Object.isFrozen(normalized.symbols[0].position)).toBe(true)
  })

  it('accepts empty geometry collections', () => {
    const empty = clone(fixture)
    for (const key of ['walls', 'rooms', 'symbols', 'routes']) empty[key] = []
    expect(normalizeCanonicalGeometry(empty)).toEqual(empty)
  })

  it.each([
    [['schema_version'], 2],
    [['project_id'], true],
    [['project_id'], Number.MAX_SAFE_INTEGER + 1],
    [['floor', 'elevation_meters'], Number.NaN],
    [['coordinate_system', 'unit'], 'pixel'],
    [['coordinate_system', 'pixels_per_meter'], 0],
    [['coordinate_system', 'width_meters'], 7],
    [['walls', 0, 'length_meters'], 3],
    [['walls', 0, 'angle_degrees'], Number.POSITIVE_INFINITY],
    [['walls', 0, 'height_meters'], 0],
    [['rooms', 0, 'boundary'], [{ x: 0, y: 0 }]],
    [['symbols', 0, 'source_type'], 'raw'],
    [['symbols', 0, 'status'], 'deleted'],
    [['symbols', 0, 'class', 'id'], -1],
    [['routes', 0, 'points'], []],
    [['routes', 0, 'points', 0, 'project_floor_id'], false],
    [['routes', 0, 'points', 0, 'elevation_meters'], Number.NEGATIVE_INFINITY],
  ])('rejects malformed contract value %#', (path, value) => {
    expect(() => normalizeCanonicalGeometry(changed(path, value))).toThrow('The canonical geometry document is invalid.')
  })

  it('rejects missing, unknown, and malformed objects and arrays', () => {
    const missing = clone(fixture)
    delete missing.routes
    const unknown = { ...clone(fixture), surprise: true }
    const malformed = changed(['walls'], {})
    for (const value of [missing, unknown, malformed, null, []]) {
      expect(() => normalizeCanonicalGeometry(value)).toThrow(TypeError)
    }
  })

  it('enforces detected/manual provenance and polygon closure rules', () => {
    const wrongIdentity = changed(['symbols', 1, 'id'], 'detected:601')
    const closedRoom = clone(fixture)
    closedRoom.rooms[0].boundary.push(clone(closedRoom.rooms[0].boundary[0]))
    for (const value of [wrongIdentity, closedRoom]) {
      expect(() => normalizeCanonicalGeometry(value)).toThrow(TypeError)
    }
  })
})
