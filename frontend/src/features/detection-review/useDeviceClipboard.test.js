import { describe, expect, it } from 'vitest'
import { deviceClipboardSnapshot, pastedDevice } from './useDeviceClipboard.js'

describe('device clipboard geometry', () => {
  const plane = { width_pixels: 400, height_pixels: 300 }
  const original = { id: 'symbol-1', center: { x: 400, y: 300 }, disposition: 'accepted',
    symbol_legend_id: 9, custom_unit_price: 10, mounting_height_meters: 1.2,
    mounting_wall_id: 'wall-1', gang_count_confirmed: true, circuit_id: 'C1' }
  it('copies device properties without source identity, approval, wall or circuit binding', () => {
    const snapshot = deviceClipboardSnapshot(original)
    expect(snapshot).toEqual({ center: original.center, symbol_legend_id: 9, custom_unit_price: 10, mounting_height_meters: 1.2,gang_count_confirmed:true })
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
  it('places at the source-space pointer and separates repeated/overlapping copies without attaching wires',()=>{
    const snapshot=deviceClipboardSnapshot(original)
    const draft={symbols:[original],wirings:[{points:[{x:100,y:80},{x:150,y:80}]}]}
    const pointer={x:200,y:150}
    const first=pastedDevice(snapshot,draft,plane,'manual-symbol-0001',pointer)
    expect(first.center).toEqual(pointer)
    draft.symbols.push(first)
    const second=pastedDevice(snapshot,draft,plane,'manual-symbol-0002',pointer)
    expect(second.center).not.toEqual(pointer)
    expect(second.id).not.toBe(first.id)
    expect(second).not.toHaveProperty('circuit_id')
    const nearTerminal=pastedDevice(snapshot,draft,plane,'manual-symbol-0003',{x:100,y:80})
    expect(nearTerminal.center).not.toEqual({x:100,y:80})
    expect(pastedDevice(snapshot,draft,plane,'manual-symbol-0004',{x:-1,y:5})).not.toBeNull()
  })
})
