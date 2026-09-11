import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { normalizeCanonicalGeometry } from './canonicalGeometry.js'
import {
  composeCanonicalView,
  normalizeCanonicalExtension,
  preserveExtensionOnSymbolMove,
} from './canonicalExtension.js'

const baseFixture = JSON.parse(
  readFileSync(new URL('../../../fixtures/canonical_geometry_v1.json', import.meta.url), 'utf8')
)
const extV2Fixture = JSON.parse(
  readFileSync(new URL('../../../fixtures/canonical_extension_v2.json', import.meta.url), 'utf8')
)
const emptyFixture = JSON.parse(
  readFileSync(new URL('../../../fixtures/canonical_extension_v2_empty.json', import.meta.url), 'utf8')
)
const partialFixture = JSON.parse(
  readFileSync(new URL('../../../fixtures/canonical_extension_v2_partial.json', import.meta.url), 'utf8')
)
const malformedFixture = JSON.parse(
  readFileSync(new URL('../../../fixtures/canonical_extension_v2_malformed.json', import.meta.url), 'utf8')
)
const unsupportedFixture = JSON.parse(
  readFileSync(new URL('../../../fixtures/canonical_extension_v2_unsupported.json', import.meta.url), 'utf8')
)

describe('normalizeCanonicalExtension', () => {
  const base = normalizeCanonicalGeometry(baseFixture)

  it('accepts the representative canonical extension v2 fixture matching base', () => {
    const normalized = normalizeCanonicalExtension(extV2Fixture, base)
    expect(normalized.extension_schema_version).toBe(2)
    expect(normalized.base_schema_version).toBe(1)
    expect(normalized.openings).toHaveLength(1)
    expect(normalized.panels).toHaveLength(1)
    expect(normalized.symbol_details).toHaveLength(2)
    expect(normalized.route_details).toHaveLength(1)
  })

  it('accepts empty extension fixture', () => {
    const normalized = normalizeCanonicalExtension(emptyFixture, base)
    expect(normalized.openings).toEqual([])
    expect(normalized.panels).toEqual([])
    expect(normalized.symbol_details).toEqual([])
    expect(normalized.route_details).toEqual([])
  })

  it('accepts partial extension fixture', () => {
    const normalized = normalizeCanonicalExtension(partialFixture, base)
    expect(normalized.openings).toHaveLength(1)
    expect(normalized.openings[0].opening_type).toBe('unknown')
  })

  it('rejects malformed extension fixture fail-closed', () => {
    expect(() => normalizeCanonicalExtension(malformedFixture, base)).toThrow(TypeError)
  })

  it('rejects unsupported extension version fail-closed', () => {
    expect(() => normalizeCanonicalExtension(unsupportedFixture, base)).toThrow(TypeError)
  })

  it('rejects symbol details referencing non-existent base symbols', () => {
    const invalid = {
      ...extV2Fixture,
      symbol_details: [{ symbol_id: 'detected:99999', orientation_degrees: null, bounds: null, provenance: null }],
    }
    expect(() => normalizeCanonicalExtension(invalid, base)).toThrow(TypeError)
  })

  it('rejects route details referencing non-existent base routes', () => {
    const invalid = {
      ...extV2Fixture,
      route_details: [{ route_id: 99999, route_kind: 'observed', provenance_ref: null }],
    }
    expect(() => normalizeCanonicalExtension(invalid, base)).toThrow(TypeError)
  })

  it('rejects openings referencing non-existent base walls', () => {
    const invalid = {
      ...extV2Fixture,
      openings: [
        {
          id: 1,
          source_candidate_id: null,
          opening_type: 'door',
          start: { x: 0.1, y: 0.1 },
          end: { x: 0.9, y: 0.1 },
          associated_wall_id: 99999,
        },
      ],
    }
    expect(() => normalizeCanonicalExtension(invalid, base)).toThrow(TypeError)
  })

  it('rejects dimension mismatch between source plane and base coordinate system', () => {
    const mismatch = {
      ...extV2Fixture,
      source_plane_reference: {
        ...extV2Fixture.source_plane_reference,
        width_pixels: 1000,
      },
    }
    expect(() => normalizeCanonicalExtension(mismatch, base)).toThrow(TypeError)
  })

  it('enforces deep immutability on returned extension object', () => {
    const normalized = normalizeCanonicalExtension(extV2Fixture, base)
    expect(Object.isFrozen(normalized)).toBe(true)
    expect(() => {
      normalized.extension_schema_version = 99
    }).toThrow()
  })
})

describe('composeCanonicalView', () => {
  const base = normalizeCanonicalGeometry(baseFixture)

  it('composes base geometry with validated extension', () => {
    const view = composeCanonicalView(base, extV2Fixture)
    expect(view.schema_version).toBe(1)
    expect(view.extension).not.toBeNull()
    expect(view.extension.extension_schema_version).toBe(2)
  })

  it('returns null extension if none provided', () => {
    const view = composeCanonicalView(base, null)
    expect(view.schema_version).toBe(1)
    expect(view.extension).toBeNull()
  })
})

describe('preserveExtensionOnSymbolMove', () => {
  it('preserves extension state across symbol moves', () => {
    const preserved = preserveExtensionOnSymbolMove(extV2Fixture, 'detected:501', { x: 3.0, y: 2.0 })
    expect(preserved).toEqual(extV2Fixture)
  })
})
