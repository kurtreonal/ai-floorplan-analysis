import { describe, expect, it } from 'vitest'

import { fitCanvas, stagePointToSource, symbolPresentation, symbolRectangle, wallLinePoints } from './detectionCanvasGeometry.js'

describe('detection canvas geometry', () => {
  it('fits without changing aspect ratio', () => {
    expect(fitCanvas(1000, 500, 500, 500)).toEqual({ scale: 0.5, width: 500, height: 250 })
    expect(fitCanvas(1000, 500, 2000, 600)).toEqual({ scale: 1.2, width: 1200, height: 600 })
  })

  it('keeps pending machine styling and distinguishes confirmed and deleted reviews', () => {
    expect(symbolPresentation({ status: 'needs_review', review: null }).color).toBe('#b54708')
    expect(symbolPresentation({ status: 'detected', review: { decision: 'confirmed' } }).color).toBe('#297a4a')
    expect(symbolPresentation({ status: 'detected', review: { decision: 'deleted' } }).color).toBe('#6b7280')
  })

  it('returns source-coordinate wall and symbol geometry unchanged', () => {
    expect(wallLinePoints({ raw_pixels: { start: { x: 1, y: 2 }, end: { x: 3, y: 4 } } })).toEqual([1, 2, 3, 4])
    expect(symbolRectangle({ bounding_box: { x_min: 2, y_min: 3, x_max: 8, y_max: 10 } })).toEqual({ x: 2, y: 3, width: 6, height: 7 })
  })

  it('rejects invalid dimensions and coordinates', () => {
    expect(() => fitCanvas(0, 1, 1, 1)).toThrow()
    expect(() => symbolRectangle({ bounding_box: { x_min: 3, y_min: 0, x_max: 2, y_max: 1 } })).toThrow()
  })

  it('converts responsive stage coordinates to deterministic source pixels', () => {
    expect(stagePointToSource({ x: 125.125, y: 50.25 }, 0.5, 1000, 800)).toEqual({ x: 250.25, y: 100.5 })
    expect(() => stagePointToSource(null, 1, 100, 80)).toThrow()
    expect(() => stagePointToSource({ x: 101, y: 1 }, 1, 100, 80)).toThrow()
  })
})
