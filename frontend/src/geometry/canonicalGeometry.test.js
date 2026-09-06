import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import {
  canonicalGeometriesEqual,
  moveCanonicalSymbol,
  normalizeCanonicalGeometry,
} from './canonicalGeometry.js'

const fixture = JSON.parse(readFileSync(new URL('../../../fixtures/canonical_geometry_v1.json', import.meta.url), 'utf8'))
const compatibilityFixture = JSON.parse(readFileSync(new URL('../../../fixtures/canonical_geometry_compatibility_v1.json', import.meta.url), 'utf8'))
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

  it('shares the v1-native and reserved-v2 compatibility decision with Python', () => {
    expect(compatibilityFixture.decision_fixture_version).toBe(1)
    expect(compatibilityFixture.current_contract).toEqual({
      schema_version: 1,
      document_fixture: 'canonical_geometry_v1.json',
      python_expectation: 'accept',
      javascript_expectation: 'accept',
      storage_behavior: 'read_native_without_rewrite',
    })
    expect(normalizeCanonicalGeometry(fixture)).toEqual(fixture)
    const future = { ...clone(fixture), schema_version: compatibilityFixture.reserved_contract.extension_schema_version }
    expect(() => normalizeCanonicalGeometry(future)).toThrow('The canonical geometry document is invalid.')
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

describe('moveCanonicalSymbol', () => {
  it('moves detected and manual symbols while preserving all other canonical data', () => {
    const original = clone(fixture)
    const detected = moveCanonicalSymbol(original, 'detected:501', { x: 0, y: 4.8 })
    const manual = moveCanonicalSymbol(detected, 'manual:601', { x: 6.4, y: 0 })
    expect(detected.symbols[0].position).toEqual({ x: 0, y: 4.8 })
    expect(manual.symbols[1].position).toEqual({ x: 6.4, y: 0 })
    expect(original).toEqual(fixture)
    const expected = clone(fixture)
    expected.symbols[0].position = { x: 0, y: 4.8 }
    expected.symbols[1].position = { x: 6.4, y: 0 }
    expect(manual).toEqual(expected)
    expect(Object.isFrozen(manual.symbols[1].position)).toBe(true)
  })

  it('normalizes to nine decimals and reports deterministic no-op equality', () => {
    const moved = moveCanonicalSymbol(fixture, 'detected:501', { x: 1.1234567894, y: 2.1234567896 })
    expect(moved.symbols[0].position).toEqual({ x: 1.123456789, y: 2.12345679 })
    const same = moveCanonicalSymbol(moved, 'detected:501', { ...moved.symbols[0].position })
    expect(canonicalGeometriesEqual(moved, same)).toBe(true)
    expect(canonicalGeometriesEqual(moved, fixture)).toBe(false)
  })

  it.each([
    ['detected:501', { x: -1, y: 0 }],
    ['detected:501', { x: 6.400000001, y: 0 }],
    ['detected:501', { x: Number.NaN, y: 0 }],
    ['detected:501', { x: Number.POSITIVE_INFINITY, y: 0 }],
    ['detected:501', { x: '1', y: 0 }],
    ['unknown:501', { x: 1, y: 1 }],
    ['detected:999', { x: 1, y: 1 }],
  ])('rejects invalid move input %#', (symbolId, position) => {
    expect(() => moveCanonicalSymbol(fixture, symbolId, position)).toThrow(TypeError)
  })

  it('rejects ambiguous canonical IDs', () => {
    const duplicate = clone(fixture)
    duplicate.symbols.push(clone(duplicate.symbols[0]))
    expect(() => moveCanonicalSymbol(duplicate, 'detected:501', { x: 1, y: 1 })).toThrow(TypeError)
  })
})
