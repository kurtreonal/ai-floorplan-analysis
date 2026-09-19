import { expect, it } from 'vitest'
import { projectRoute, routeWorldPositions } from './routeProjection.js'

it('uses stored aligned segments and hides stale or unrelated snapshots', () => {
  const record = { stale: false, layout_versions: { 2: 10 }, configuration: { floors: [{ floor_id: 2, offset_x: 4, offset_y: 1 }] },
    result: { segments: [{ kind: 'wall_drop', start: { floor_id: 2, x: 5, y: 3, elevation_meters: 3 }, end: { floor_id: 2, x: 5, y: 3, elevation_meters: .3 } }] } }
  const layout = { id: 10, project_floor_id: 2 }
  const segments = projectRoute(record, layout)
  expect(segments[0].start).toEqual({ floor_id: 2, x: 1, y: 2, elevation_meters: 3 })
  expect(segments[0].end.elevation_meters).toBe(.3)
  expect(routeWorldPositions(segments[0])).toEqual([1, 3, 2, 1, .3, 2])
  expect(record.result.segments[0].start.x).toBe(5)
  expect(projectRoute({ ...record, stale: true }, layout)).toEqual([])
  expect(projectRoute(record, { ...layout, id: 11 })).toEqual([])
})
