import { expect, it } from 'vitest'
import { MAX_ROUTE_OBSTACLES, normalizeRouteObstacles, obstacleRows, routingObstaclesFromRows } from './routeObstacles.js'

const obstacle = { floor_id: 2, min_x: 1, min_y: 2, max_x: 3, max_y: 4, bottom: -1, top: 0 }

it('round-trips explicit metric obstacles without modifying their source', () => {
  const source = Object.freeze([Object.freeze(obstacle)])
  expect(routingObstaclesFromRows(obstacleRows(source, 2), 2)).toEqual(source)
  expect(normalizeRouteObstacles(source, 2)).toEqual(source)
  expect(normalizeRouteObstacles(undefined, 2)).toEqual([])
  expect(routingObstaclesFromRows([], 2)).toEqual([])
  expect(MAX_ROUTE_OBSTACLES).toBe(128)
})

it.each([
  ['foreign floor', { ...obstacle, floor_id: 3 }],
  ['string floor', { ...obstacle, floor_id: '2' }],
  ['unknown field', { ...obstacle, approval: true }],
  ['missing bound', { floor_id: 2, min_x: 1, min_y: 2, max_x: 3, max_y: 4, top: 0 }],
  ['string bound', { ...obstacle, min_x: '1' }],
  ['NaN', { ...obstacle, min_x: NaN }],
  ['infinity', { ...obstacle, max_y: Infinity }],
  ['zero width', { ...obstacle, max_x: 1 }],
  ['reversed y', { ...obstacle, min_y: 5 }],
  ['zero elevation span', { ...obstacle, bottom: 0 }],
  ['null', null],
])('rejects %s instead of silently dropping unsafe saved configuration', (_name, value) => {
  expect(() => normalizeRouteObstacles([value], 2)).toThrow()
})

it('bounds the list and rejects nonarrays', () => {
  expect(normalizeRouteObstacles(Array.from({ length: 128 }, () => obstacle), 2)).toHaveLength(128)
  expect(() => normalizeRouteObstacles(Array.from({ length: 129 }, () => obstacle), 2)).toThrow()
  expect(() => normalizeRouteObstacles({}, 2)).toThrow()
})

it.each(['', ' ', 'Infinity', 'NaN'])('does not coerce draft %j into a measurement', (value) => {
  const rows = obstacleRows([obstacle], 2)
  rows[0].min_x = value
  expect(() => routingObstaclesFromRows(rows, 2)).toThrow()
})
