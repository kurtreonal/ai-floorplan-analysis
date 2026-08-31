import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { normalizeCanonicalGeometry } from '../../geometry/canonicalGeometry.js'
import {
  fitSourcePlane, metricPointToPixel, metricPointsToPixels, resolveBlueprintProvenance,
} from './layoutCanvasGeometry.js'

const fixture = JSON.parse(readFileSync(new URL('../../../../fixtures/canonical_geometry_v1.json', import.meta.url), 'utf8'))

describe('canonical layout canvas geometry', () => {
  it('converts zero, boundary, and non-default metric coordinates to source pixels', () => {
    const cs = fixture.coordinate_system
    expect(metricPointToPixel({ x: 0, y: 0 }, cs)).toEqual({ x: 0, y: 0 })
    expect(metricPointToPixel({ x: 6.4, y: 4.8 }, cs)).toEqual({ x: 640, y: 480 })
    expect(metricPointsToPixels([{ x: .25, y: .5 }, { x: 1, y: 2 }], cs)).toEqual([25, 50, 100, 200])
  })

  it('fits responsively without changing aspect ratio', () => {
    expect(fitSourcePlane(640, 480, 320, 500)).toEqual({ scale: .5, width: 320, height: 240 })
    expect(fitSourcePlane(640, 480, 1000, 240)).toEqual({ scale: .5, width: 320, height: 240 })
  })

  it('rejects invalid, non-finite, and out-of-bounds inputs', () => {
    expect(() => fitSourcePlane(0, 1, 1, 1)).toThrow()
    expect(() => metricPointToPixel({ x: Number.NaN, y: 0 }, fixture.coordinate_system)).toThrow()
    expect(() => metricPointToPixel({ x: 6.41, y: 0 }, fixture.coordinate_system)).toThrow()
  })

  it('resolves only one unambiguous safe processing job without mutating geometry', () => {
    const geometry = normalizeCanonicalGeometry(fixture)
    expect(resolveBlueprintProvenance(geometry)).toEqual({ floorPlanId: 81, processingJobId: 103 })
    expect(Object.isFrozen(geometry)).toBe(true)
    const mixed = structuredClone(fixture)
    mixed.symbols[1].processing_job_id = 104
    expect(resolveBlueprintProvenance(normalizeCanonicalGeometry(mixed))).toBeNull()
    const sourceLess = structuredClone(fixture)
    sourceLess.walls = []
    sourceLess.symbols = []
    expect(resolveBlueprintProvenance(normalizeCanonicalGeometry(sourceLess))).toBeNull()
  })
})
