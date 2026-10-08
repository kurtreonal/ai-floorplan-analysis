import { expect, it } from 'vitest'
import { projectRoute, routeAppearance, routeWorldPositions } from './routeProjection.js'

it('shares explicit installation colors without treating unknown wiring as ceiling service', () => {
  expect(routeAppearance('ceiling_service')).toMatchObject({ color: '#f05a28', dashed: false })
  expect(routeAppearance('wall_drop')).toEqual(routeAppearance('wall_rise'))
  expect(routeAppearance('riser').color).toBe('#9c36b5')
  expect(routeAppearance('underground')).toMatchObject({ color: '#2563eb', dashed: true })
  expect(routeAppearance('underground_drop')).toEqual(routeAppearance('underground_rise'))
  for (const kind of [undefined, 'observed', 'downlight']) {
    expect(routeAppearance(kind)).toMatchObject({ color: '#8a5a00', label: expect.stringContaining('unresolved') })
  }
})

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
