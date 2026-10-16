import { describe, expect, it } from 'vitest'
import { deviceClipboardSnapshot, pastedDevice } from './useDeviceClipboard.js'

describe('device clipboard geometry', () => {
  const plane = { width_pixels: 400, height_pixels: 300 }
  const original = { id: 'symbol-1', center: { x: 400, y: 300 }, disposition: 'accepted',
    symbol_legend_id: 9, custom_unit_price: 10, mounting_height_meters: 1.2,
    mounting_wall_id: 'wall-1', gang_count_confirmed: true, circuit_id: 'C1' }
  it('copies device properties without source identity, approval, wall or circuit binding', () => {
    const snapshot = deviceClipboardSnapshot(original)
    expect(snapshot).toEqual({ center: original.center, symbol_legend_id: 9, custom_unit_price: 10, mounting_height_meters: 1.2 })
    expect(snapshot.center).not.toBe(original.center)
    expect(deviceClipboardSnapshot({ ...original, disposition: 'rejected' })).toBeNull()
  })
  it('keeps repeated copies distinct, within the source page and away from wire endpoints', () => {
    const draft = { symbols: [original], wirings: [{ points: [{ x: 393, y: 293 }, { x: 200, y: 293 }] }] }
    const snapshot = deviceClipboardSnapshot(original)
    const first = pastedDevice(snapshot, draft, plane, 'manual-symbol-0001')
    draft.symbols.push(first)
    const second = pastedDevice(snapshot, draft, plane, 'manual-symbol-0002')
    expect(first.center).not.toEqual(original.center)
    expect(first.center).not.toEqual(draft.wirings[0].points[0])
    expect(second.center).not.toEqual(first.center)
    for (const copy of [first, second]) {
      expect(copy.center.x).toBeLessThanOrEqual(400)
      expect(copy.center.y).toBeLessThanOrEqual(300)
      expect(copy).toMatchObject({ disposition: 'added', symbol_legend_id: 9 })
      expect(copy).not.toHaveProperty('mounting_wall_id')
    }
  })
})
