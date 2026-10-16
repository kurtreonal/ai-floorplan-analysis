import { expect, it } from 'vitest'
import { bindCircuitMounting } from './circuitMounting.js'
import { devicePlacement } from './devicePlacement.js'
import { projectRoute, routeWorldPositions } from '../routing/routeProjection.js'

const scene = { elevation: 0, width: 10, depth: 10, walls: [], symbols: [{ id: 's', position: [2, 0, 1] }] }
const layout = { id: 5, project_id: 1, project_floor_id: 2, geometry: { symbols: [{ id: 's', position: { x: 2, y: 1 } }] } }
const record = { id: 7, project_id: 1, layout_versions: { 2: 5 }, stale: false,
  configuration: { targets: [{ floor_id: 2, symbol_id: 's', x: 2, y: 1, elevation_meters: 2.7, wall_id: null }] },
  result: { status: 'saved_planning', algorithm: 'greedy_shared_service_tree_v1' } }

it('binds explicit saved and preview elevations without changing canonical anchors', () => {
  const original = structuredClone(scene)
  for (const status of ['preview_not_saved', 'saved_planning']) {
    const bound = bindCircuitMounting(scene, { ...record, result: { ...record.result, status } }, layout)
    const light = devicePlacement(bound.symbols[0], bound, 'troffer')
    expect(light.position).toEqual([2, 2.7 - 0.045, 1])
    expect(devicePlacement(bound.symbols[0], bound, 'switch').position).toEqual([2, 2.7, 1])
    expect(bound.symbols[0].installation.provenance).toBe('designer_supplied_planning')
  }
  expect(scene).toEqual(original)
})

it.each([{ stale: true }, { project_id: 9 }, { layout_versions: { 2: 9 } }])('ignores stale and unrelated metadata %j', (patch) => {
  expect(bindCircuitMounting(scene, { ...record, ...patch }, layout)).toBe(scene)
})

it('ignores mismatched XY, unresolved walls and other-floor targets', () => {
  for (const patch of [{ x: 99 }, { wall_id: 123 }, { floor_id: 9 }, { elevation_meters: NaN }]) {
    const bound = bindCircuitMounting(scene, { ...record, configuration: { targets: [{ ...record.configuration.targets[0], ...patch }] } }, layout)
    expect(bound.symbols[0]).toBe(scene.symbols[0])
  }
})

it('also binds a saved single-target A* route to its explicit installation', () => {
  const single = { ...record, configuration: { purpose: 'planning',target: record.configuration.targets[0] },result: { segments: [] } }
  expect(bindCircuitMounting(scene,single,layout).symbols[0].installation).toMatchObject({ elevation_meters: 2.7,state: 'saved_planning' })
  expect(bindCircuitMounting(scene,{ ...single,result: { segments: [],algorithm: 'unknown' } },layout)).toBe(scene)
})

it.each(['assigned_missing_device_astar_v1', 'assigned_missing_device_astar_v2'])('binds only actual missing-device branches for %s, never overriding a skipped source connection', (algorithm) => {
  const pending = { ...record, result: { ...record.result, algorithm, branches: [] } }
  expect(bindCircuitMounting(scene, pending, layout).symbols[0]).toBe(scene.symbols[0])
  pending.result.branches = [{ floor_id: 2, symbol_id: 's' }]
  const bound = bindCircuitMounting(scene, pending, layout)
  expect(devicePlacement(bound.symbols[0], bound, 'switch').position).toEqual([2, 2.7, 1])
})

it.each(['assigned_missing_device_astar_v1', 'assigned_missing_device_astar_v2'])('projects a missing-device drop for %s from one saved route record into 2D and 3D unchanged', (algorithm) => {
  const drop = { kind: 'wall_drop', start: { floor_id: 2, x: 2, y: 1, elevation_meters: 3 },
    end: { floor_id: 2, x: 2, y: 1, elevation_meters: 1.2 } }
  const saved = { ...record, configuration: { ...record.configuration,
    floors: [{ floor_id: 2, offset_x: 0, offset_y: 0 }],
    targets: [{ ...record.configuration.targets[0], elevation_meters: 1.2 }] },
    result: { ...record.result, algorithm, segments: [drop],
      branches: [{ floor_id: 2, symbol_id: 's' }] } }
  const before = structuredClone(saved)
  const projected = projectRoute(saved, layout)
  expect(projected).toEqual([drop])
  expect(routeWorldPositions(projected[0])).toEqual([2, 3, 1, 2, 1.2, 1])
  const bound = bindCircuitMounting(scene, saved, layout)
  expect(devicePlacement(bound.symbols[0], bound, 'switch').position).toEqual([2, 1.2, 1])
  expect(saved).toEqual(before)
  expect(projectRoute({ ...saved, stale: true }, layout)).toEqual([])
})
