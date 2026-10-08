import { describe, expect, it } from 'vitest'
import { drawingRegionFromPoints } from './drawingRegion.js'

describe('source drawing rectangle', () => {
  it('normalizes reversed corners and includes fractional boundary pixels', () => {
    expect(drawingRegionFromPoints({ x: 95.2, y: 80.7 }, { x: 10.9, y: 20.5 }, 200, 100))
      .toEqual({ x: 10, y: 20, width: 86, height: 61 })
  })
  it('clamps source bounds without inventing a non-empty region', () => {
    expect(drawingRegionFromPoints({ x: -10, y: -20 }, { x: 500, y: 300 }, 200, 100))
      .toEqual({ x: 0, y: 0, width: 200, height: 100 })
    expect(drawingRegionFromPoints({ x: 5, y: 5 }, { x: 5, y: 5 }, 200, 100)).toBeNull()
    expect(drawingRegionFromPoints({ x: NaN, y: 5 }, { x: 25, y: 30 }, 200, 100)).toBeNull()
  })
})
