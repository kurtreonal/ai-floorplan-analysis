import { expect, it } from 'vitest'
import { RouteLines3D } from './RouteLines3D.jsx'

it('renders stored elevations and distinct ceiling/wall styles with normal depth occlusion', () => {
  const start = { x: 1, y: 2, elevation_meters: 3 }
  const segments = [
    { kind: 'ceiling_service', start, end: { ...start, x: 4 } },
    { kind: 'wall_drop', start, end: { ...start, elevation_meters: .4 } },
  ]
  const before = JSON.stringify(segments)
  const lines = RouteLines3D({ segments }).props.children
  expect(lines[0].props.children[1].type).toBe('lineBasicMaterial')
  expect(lines[0].props.children[1].props.color).toBe('#f05a28')
  const wall = lines[1].props.children
  expect(Array.from(wall[0].props.children[0].props.args[0])).toEqual([1, 3, 2, 1, expect.closeTo(.4), 2])
  expect(Array.from(wall[0].props.children[1].props.args[0])).toEqual([0, expect.closeTo(2.6)])
  expect(wall[1].type).toBe('lineDashedMaterial')
  expect(wall[1].props.depthTest).toBeUndefined()
  expect(JSON.stringify(segments)).toBe(before)
})

it('keeps underground depth unchanged and enables X-ray only by explicit inspection', () => {
  const start = { x: 1, y: 2, elevation_meters: -.4 }
  const segments = [
    { kind: 'underground', start, end: { ...start, x: 4 } },
    { kind: 'wall_rise', start: { ...start, elevation_meters: 0 }, end: { ...start, elevation_meters: 1.2 } },
  ]
  const regular = RouteLines3D({ segments }).props.children
  const inspected = RouteLines3D({ segments, inspectUnderground: true }).props.children
  expect(regular[0].props.children[1].props.depthTest).toBeUndefined()
  expect(inspected[0].props.children[1].props).toMatchObject({ color: '#2563eb', depthTest: false, depthWrite: false })
  expect(inspected[0].props.renderOrder).toBe(10)
  expect(inspected[1].props.children[1].props.depthTest).toBeUndefined()
  expect(Array.from(inspected[0].props.children[0].props.children[0].props.args[0])).toEqual([1, expect.closeTo(-.4), 2, 4, expect.closeTo(-.4), 2])
})
