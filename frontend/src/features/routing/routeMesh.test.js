import { expect, it } from 'vitest'
import { Vector3, Quaternion } from 'three'
import { routeCylinder, ROUTE_DISPLAY_RADIUS } from './routeMesh.js'

it.each([
  [[1, 3, 2], [5, 3, 2]],
  [[5, 3, 2], [5, 1.2, 2]],
  [[1, -.5, 2], [1, -.5, 6]],
])('tube ends match exact ceiling/wall/underground route coordinates', (start, end) => {
  const mesh = routeCylinder(start, end)
  const axis = new Vector3(0, mesh.length / 2, 0).applyQuaternion(new Quaternion(...mesh.quaternion))
  const midpoint = new Vector3(...mesh.position)
  midpoint.clone().sub(axis).toArray().forEach((v, i) => expect(v).toBeCloseTo(start[i]))
  midpoint.clone().add(axis).toArray().forEach((v, i) => expect(v).toBeCloseTo(end[i]))
  expect(ROUTE_DISPLAY_RADIUS).toBeLessThan(.02)
})
it('rejects invalid coordinates and omits degenerate segments', () => {
  expect(routeCylinder([1, 2, 3], [1, 2, 3])).toBeNull()
  expect(() => routeCylinder([NaN, 2, 3], [1, 2, 3])).toThrow()
})
