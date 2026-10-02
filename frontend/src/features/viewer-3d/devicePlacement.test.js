import { describe, expect, it } from 'vitest'
import { devicePlacement, sceneCeiling } from './devicePlacement.js'
import { buildDraftRoomScene } from '../detection-review/draftRoomScene.js'
import { roofPreview } from './roofPreview.js'
import { deviceDragPosition, startDeviceDrag } from './deviceDrag.js'
import { Ray, Vector3 } from 'three'

const wall = { id: 'w', position: [5, 1.35, 0], size: [10, 2.7, 0.18], rotation: [0, 0, 0] }
const scene = { width: 10, depth: 20, elevation: 0, extent: 20, walls: [wall], rooms: [] }
const symbol = { id: 's', position: [3, 0, 4] }
describe('physical preview device placement', () => {
  it('mounts a 600 x 1200 mm troffer under the actual wall top, independent of page extent', () => {
    const before = structuredClone(symbol)
    const a = devicePlacement(symbol, scene, 'troffer')
    expect(a.size).toEqual([0.6, 0.09, 1.2])
    expect(a.position[1] + a.size[1] / 2).toBeCloseTo(2.7)
    expect(a.position[0]).toBe(3); expect(a.position[2]).toBe(4)
    expect(devicePlacement(symbol, { ...scene, extent: 1000 }, 'troffer').size).toEqual(a.size)
    expect(sceneCeiling(scene)).toBe(2.7)
    expect(symbol).toEqual(before)
  })
  it.each([['outlet', 0.3], ['switch', 1.2], ['panel', 1.5], ['pull-station', 1.2], ['alarm', 2.2]])('places %s vertically at its default mounting height', (family, height) => {
    const placement = devicePlacement({ ...symbol, position: [3, 0, 0] }, scene, family)
    expect(placement.position[1]).toBe(height)
    expect(placement.position[2] - placement.size[2] / 2).toBeGreaterThan(0.09)
    expect(placement.rotation).toBeCloseTo(0)
  })
  it('does not snap remote devices to unrelated walls and respects negative floor elevations', () => {
    expect(devicePlacement(symbol, scene, 'outlet').anchorOffset).toEqual([0, 0])
    const lower = { ...scene, elevation: -3, walls: [{ ...wall, position: [5, -1.65, 0] }] }
    expect(devicePlacement({ ...symbol, position: [3, -3, 4] }, lower, 'switch').position[1]).toBeCloseTo(-1.8)
    expect(devicePlacement(symbol, lower, 'troffer').position[1]).toBeCloseTo(-0.345)
  })
  it('keeps preview metres proportional, mounting stable when walls are hidden, and source anchors unchanged', () => {
    const draft = { rooms: [], walls: [{ id: 'w', start: { x: 0, y: 0 }, end: { x: 100, y: 0 } }], symbols: [{ id: 's', center: { x: 50, y: 50 } }] }
    const preview = buildDraftRoomScene(draft, 100, 200, 0.75, {}, { longSideMeters: 40 })
    const light = devicePlacement(preview.symbols[0], preview, 'troffer')
    expect(light.size).toEqual([0.15, 0.0225, 0.3])
    expect(light.position[1] + light.size[1] / 2).toBe(0.75)
    expect(devicePlacement(preview.symbols[0], { ...preview, walls: [] }, 'troffer')).toEqual(light)
    expect(preview.walls[0].size[2]).toBeCloseTo(0.045)
    expect(preview.symbols[0].position).toEqual([2.5, 0, 2.5])
  })
  it('raised dragging recovers the same XY anchor, including the wall-face visual offset', () => {
    const placed = devicePlacement({ ...symbol, position: [3, 0, 0] }, scene, 'outlet')
    const ray = (x, z) => new Ray(new Vector3(x, 10, z), new Vector3(0, -1, 0))
    const drag = startDeviceDrag(ray(placed.position[0], placed.position[2]), placed.position)
    const moved = deviceDragPosition(ray(4, placed.position[2] + 2), drag, scene)
    expect(moved.x - placed.anchorOffset[0]).toBe(4)
    expect(moved.z - placed.anchorOffset[1]).toBeCloseTo(2)
    expect(drag.plane.constant).toBe(-0.3)
  })
  it('builds roof covers from room footprints, with an explicitly simple wall-envelope fallback', () => {
    const room = { id: 'r', boundary: [{ x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 5 }] }
    expect(roofPreview({ ...scene, rooms: [room] })).toEqual([{ ...room, elevation: 2.7 }])
    expect(roofPreview(scene)).toEqual([]) // a lone line is not a roof footprint
    const roof = roofPreview({ ...scene, walls: [wall, { ...wall, position: [5, 1.35, 10] }] })
    expect(roof[0].boundary).toEqual([{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }])
  })
})
