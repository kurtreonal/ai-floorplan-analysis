import { expect, it, vi } from 'vitest'
import { RouteLines3D } from './RouteLines3D.jsx'
vi.mock('react', async importOriginal => ({...await importOriginal(),useMemo:fn=>fn()}))

it('renders stored elevations and distinct ceiling/wall styles with normal depth occlusion', () => {
  const start = { x: 1, y: 2, elevation_meters: 3 }
  const segments = [
    { kind: 'ceiling_service', start, end: { ...start, x: 4 } },
    { kind: 'wall_drop', start, end: { ...start, elevation_meters: .4 } },
  ]
  const before = JSON.stringify(segments)
  const lines = RouteLines3D({ segments }).props.children
  const ceilingTube = lines[0].props.children[0]
  expect(ceilingTube.props.run.points).toEqual([[1,3,2],[4,3,2]])
  expect(ceilingTube.props.color).toBe('#f05a28')
  const wall = lines[1].props.children
  expect(wall[0].props.run.points).toEqual([[1,3,2],[1,.4,2]])
  expect(Array.from(wall[1].props.children[0].props.children[0].props.args[0])).toEqual([1, 3, 2, 1, expect.closeTo(.4), 2])
  expect(Array.from(wall[1].props.children[0].props.children[1].props.args[0])).toEqual([0, expect.closeTo(2.6)])
  expect(wall[1].props.children[1].type).toBe('lineDashedMaterial')
  expect(wall[0].props.xray).toBe(false)
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
  expect(regular[0].props.children[0].props.xray).toBe(false)
  expect(inspected[0].props.children[0].props).toMatchObject({ color: '#2563eb', xray:true })
  expect(inspected[1].props.children[0].props.xray).toBe(false)
  expect(Array.from(inspected[0].props.children[1].props.children[0].props.children[0].props.args[0])).toEqual([1, expect.closeTo(-.4), 2, 4, expect.closeTo(-.4), 2])
})

it('preserves every underground bend in the continuous tube and dashed inspection trace', () => {
  const points=[{x:0,y:0,elevation_meters:-.4},{x:3,y:0,elevation_meters:-.4},{x:3,y:4,elevation_meters:-.4}]
  const segments=points.slice(1).map((end,index)=>({route_id:'buried',kind:'underground',start:points[index],end}))
  const before=structuredClone(segments)
  const runs=RouteLines3D({segments}).props.children
  expect(runs).toHaveLength(1)
  const [tube,inspection]=runs[0].props.children
  expect(tube.props.run.points).toEqual([[0,-.4,0],[3,-.4,0],[3,-.4,4]])
  const [position,distance]=inspection.props.children[0].props.children
  expect(Array.from(position.props.args[0])).toEqual([0,expect.closeTo(-.4),0,3,expect.closeTo(-.4),0,3,expect.closeTo(-.4),4])
  expect(Array.from(distance.props.args[0])).toEqual([0,3,7])
  expect(segments).toEqual(before)
})
