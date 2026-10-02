import { describe, expect, it } from 'vitest'
import { clampDevicePoint, describeReviewSymbol, deviceFamily, reviewGeometryPayload } from './devicePresentation.js'

describe('device presentation without class approval', () => {
  it.each([
    ['Troffer light', 'troffer'], ['Fluorescent light with reflector', 'linear-light'], ['Orientable downlight', 'round-light'],
    ['Distribution board', 'panel'], ['Panelboard', 'panel'], ['Duplex power outlet', 'outlet'], ['Three way switch', 'switch'],
    ['Smoke detector', 'detector'], ['Pull station', 'pull-station'], ['Alarm bell', 'alarm'], ['Circuit home-run notation', 'annotation'], ['Unclassified circular symbol', 'unknown'],
  ])('uses a schematic %s representation without changing its class', (name, family) => { expect(deviceFamily(name)).toBe(family) })

  const record = { candidate: { payload: { symbols: { items: [{ id: 'symbol-0001', observed_label: 'Troffer light' }] } } }, review: null }
  it('shows the original detector name as provisional until a legend is linked', () => {
    const symbol = { id: 'symbol-0001', symbol_legend_id: null, disposition: 'unresolved' }
    expect(describeReviewSymbol(symbol, record)).toEqual({ name: 'Troffer light', family: 'troffer', label: 'Troffer light · proposal', mapped: false, originalLabel: 'Troffer light' })
    expect(symbol.disposition).toBe('unresolved')
    const corrected = describeReviewSymbol({ ...symbol, symbol_legend_id: 9 }, record, [{ id: 9, class_id: 4, name: 'Power outlet' }])
    expect(corrected).toMatchObject({ name: 'Power outlet', family: 'outlet', mapped: true, originalLabel: 'Troffer light' })
  })
  it('does not reuse a saved name after unmapping or changing the legend', () => {
    const saved = { ...record, review: { symbols: [{ id: 'symbol-0001', symbol_legend_id: 9, class_name: 'Reviewed outlet' }] } }
    expect(describeReviewSymbol({ id: 'symbol-0001', symbol_legend_id: 9 }, saved).name).toBe('Reviewed outlet')
    expect(describeReviewSymbol({ id: 'symbol-0001', symbol_legend_id: null }, saved).mapped).toBe(false)
    expect(describeReviewSymbol({ id: 'symbol-0001', symbol_legend_id: 10 }, saved).name).toBe('Troffer light')
  })
  it('bounds coordinates, rejects non-finite values and strips display-only data from strict writes', () => {
    expect(clampDevicePoint({ x: -1, y: 300.9 }, 400, 300)).toEqual({ x: 0, y: 300 })
    expect(clampDevicePoint({ x: NaN, y: 0 }, 400, 300)).toBeNull()
    const draft = { walls: [{ id: 'wall-0001', disposition: 'accepted', start: { x: 0, y: 0 }, end: { x: 10, y: 0 }, estimated_thickness_pixels: 8 }], rooms: [],
      symbols: [{ id: 'symbol-0001', disposition: 'rejected', center: { x: 20, y: 30 }, symbol_legend_id: 9, class_name: 'Private legend', presentation: {} }] }
    const before = structuredClone(draft)
    const payload = reviewGeometryPayload(draft)
    expect(Object.keys(payload.walls[0])).toEqual(['id', 'disposition', 'start', 'end'])
    expect(Object.keys(payload.symbols[0])).toEqual(['id', 'disposition', 'center', 'symbol_legend_id'])
    expect(payload.symbols[0].disposition).toBe('rejected')
    expect(draft).toEqual(before)
  })
})
