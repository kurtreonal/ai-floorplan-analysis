import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { normalizeCanonicalGeometry } from '../../geometry/canonicalGeometry.js'
import {
  clampSourcePixelPoint, fitSourcePlane, metricPointToPixel, metricPointsToPixels,
  resolveBlueprintProvenance, sourcePixelPointToMetric,
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

  it('clamps the inclusive source plane and converts pixels back to meters', () => {
    const cs = fixture.coordinate_system
    expect(clampSourcePixelPoint({ x: -4, y: 900 }, cs)).toEqual({ x: 0, y: 480 })
    expect(sourcePixelPointToMetric({ x: 0, y: 0 }, cs)).toEqual({ x: 0, y: 0 })
    expect(sourcePixelPointToMetric({ x: 640, y: 480 }, cs)).toEqual({ x: 6.4, y: 4.8 })
    const custom = { ...cs, pixels_per_meter: 80, image_width_pixels: 800, image_height_pixels: 400 }
    expect(sourcePixelPointToMetric({ x: 240, y: 160 }, custom)).toEqual({ x: 3, y: 2 })
  })

  it('rejects invalid, non-finite, and out-of-bounds inputs', () => {
    expect(() => fitSourcePlane(0, 1, 1, 1)).toThrow()
    expect(() => metricPointToPixel({ x: Number.NaN, y: 0 }, fixture.coordinate_system)).toThrow()
    expect(() => metricPointToPixel({ x: 6.41, y: 0 }, fixture.coordinate_system)).toThrow()
    expect(() => clampSourcePixelPoint({ x: Number.NaN, y: 0 }, fixture.coordinate_system)).toThrow()
    expect(() => sourcePixelPointToMetric({ x: 1, y: 1 }, { ...fixture.coordinate_system, pixels_per_meter: 0 })).toThrow()
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
