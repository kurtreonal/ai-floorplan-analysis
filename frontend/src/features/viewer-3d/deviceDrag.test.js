import { describe, expect, it } from 'vitest'
import { Ray, Vector3 } from 'three'
import { deviceDragPosition, startDeviceDrag } from './deviceDrag.js'

const downRay = (x, z) => new Ray(new Vector3(x, 20, z), new Vector3(0, -1, 0))
describe('3D device planar dragging', () => {
  it('preserves grab offset and recorded floor elevation without fabricating height', () => {
    const drag = startDeviceDrag(downRay(2.1, 3.2), [2, -1.5, 3])
    expect(drag.plane.constant).toBe(1.5)
    const next = deviceDragPosition(downRay(5.1, 6.2), drag, { width: 10, depth: 8 })
    expect(next.x).toBeCloseTo(5)
    expect(next.z).toBeCloseTo(6)
  })
  it('clamps to the source extent and ignores rays parallel to the editing plane', () => {
    const drag = startDeviceDrag(downRay(2, 3), [2, 0, 3])
    expect(deviceDragPosition(downRay(-10, 20), drag, { width: 10, depth: 8 })).toEqual({ x: 0, z: 8 })
    const parallel = new Ray(new Vector3(0, 10, 0), new Vector3(1, 0, 0))
    expect(startDeviceDrag(parallel, [2, 0, 3])).toBeNull()
    expect(deviceDragPosition(parallel, drag, { width: 10, depth: 8 })).toBeNull()
  })
})
