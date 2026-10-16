import { afterEach, expect, it, vi } from 'vitest'
import { previewCircuit, saveCircuit, routingRequest } from './routing.js'

afterEach(() => vi.unstubAllGlobals())
const configuration = { circuit_id: 'C-LGT', installation_method: 'ceiling_service', targets: [{ floor_id: 2, symbol_id: 'detected:1' }] }
function response() {
  const a = { floor_id: 2, x: 1, y: 1, elevation_meters: 3 }
  const b = { ...a, x: 2 }
  return { project_id: 1, layout_versions: { 2: 5 }, configuration: { ...configuration, floors: [{ floor_id: 2 }] }, stale: false,
    result: { circuit_id: 'C-LGT', installation_method: 'ceiling_service', provenance: 'generated', status: 'preview_not_saved',
      algorithm: 'greedy_shared_service_tree_v1', optimality: 'graph_heuristic_not_global_optimum', horizontal_meters: 1, vertical_meters: 0, total_meters: 1,
      segments: [{ start: a, end: b, kind: 'ceiling_service', horizontal_meters: 1, vertical_meters: 0 }],
      branches: [{ floor_id: 2, symbol_id: 'detected:1', points: [a, b], segment_indices: [0], horizontal_meters: 1, vertical_meters: 0, total_meters: 1 }] } }
}
it('sends explicit preview inputs and abort signal without publishing a saved route', async () => {
  const record = response()
  const fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => record })
  vi.stubGlobal('fetch', fetch)
  const signal = new AbortController().signal
  expect(await previewCircuit(1, configuration, { signal })).toEqual(record)
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/api/projects/1/routes'), expect.objectContaining({
    credentials: 'include', method: 'POST', signal, body: JSON.stringify(configuration),
  }))
})

it.each(['assigned_missing_device_astar_v1', 'assigned_missing_device_astar_v2'])('validates partial %s results and rejects duplicated or omitted coverage', async (algorithm) => {
  const record = response()
  record.configuration.routing_mode = 'missing_devices'
  record.result.algorithm = algorithm
  record.result.branches = []
  record.result.segments = []
  record.result.horizontal_meters = record.result.vertical_meters = record.result.total_meters = 0
  record.result.skipped_targets = [{ floor_id: 2, symbol_id: 'detected:1', reason: 'EXISTING_CANONICAL_CONNECTION' }]
  record.result.unresolved_targets = []
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => record }))
  expect(await previewCircuit(1, record.configuration)).toEqual(record)
  record.result.unresolved_targets = [...record.result.skipped_targets]
  await expect(previewCircuit(1, record.configuration)).rejects.toThrow('Invalid circuit preview response.')
  record.result.skipped_targets = record.result.unresolved_targets = []
  await expect(previewCircuit(1, record.configuration)).rejects.toThrow('Invalid circuit preview response.')
})

it('accepts an explicit v2 device binding at its assigned tree without a duplicate zero-length wire', async () => {
  const record = response()
  record.configuration.routing_mode = 'missing_devices'
  record.result.algorithm = 'assigned_missing_device_astar_v2'
  Object.assign(record.result.branches[0], { points: [record.result.segments[0].end],
    segment_indices: [], horizontal_meters: 0, vertical_meters: 0, total_meters: 0 })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => record }))
  expect(await previewCircuit(1, record.configuration)).toEqual(record)
})
it.each(['saved', 'branch', 'nan', 'kind', 'length'])('rejects malformed or misleading %s previews', async (mutation) => {
  const record = response()
  if (mutation === 'saved') record.result.status = 'saved'
  if (mutation === 'branch') record.result.branches[0].segment_indices = [5]
  if (mutation === 'nan') record.result.segments[0].start.x = NaN
  if (mutation === 'kind') record.result.segments[0].kind = 'underground'
  if (mutation === 'length') record.result.total_meters = 99
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => record }))
  await expect(previewCircuit(1, configuration)).rejects.toThrow('Invalid circuit preview response.')
})
it('does not display an arbitrary backend exception as a user-facing error', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({ detail: { error: { code: 'private connection string' } } }) }))
  await expect(previewCircuit(1, configuration)).rejects.toThrow('Circuit preview is unavailable.')
})

it('saves and reloads the same versioned planning circuit, including a stale historical result', async () => {
  const record = response()
  Object.assign(record, { id: 7, version_number: 1 })
  Object.assign(record.configuration, { intent: 'save_planning_circuit', request_id: '123' })
  record.result.status = 'saved_planning'
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 201, json: async () => record }))
  expect(await saveCircuit(1, record.configuration)).toEqual(record)
  record.stale = true
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => record }))
  expect(await routingRequest(1)).toEqual(record)
})

it('rejects a saved circuit with invalid branch references on reload', async () => {
  const record = response()
  Object.assign(record, { id: 7, version_number: 1 })
  Object.assign(record.configuration, { intent: 'save_planning_circuit', request_id: '123' })
  record.result.status = 'saved_planning'
  record.result.branches[0].segment_indices = [99]
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => record }))
  await expect(routingRequest(1)).rejects.toThrow('Invalid circuit preview response.')
})

it('accepts explicit underground elevations and rejects unconfirmed or mismatched installation responses', async () => {
  const record = response()
  record.configuration = { ...record.configuration, installation_method: 'underground', floor_passages_confirmed: true }
  record.result.installation_method = 'underground'
  record.result.segments[0].kind = 'underground'
  record.result.segments[0].start.elevation_meters = -.4
  record.result.segments[0].end.elevation_meters = -.4
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => record }))
  expect(await previewCircuit(1, record.configuration)).toEqual(record)
  await expect(previewCircuit(1, { ...record.configuration, floor_passages_confirmed: false })).rejects.toThrow('Invalid circuit preview response.')
  await expect(previewCircuit(1, configuration)).rejects.toThrow('Invalid circuit preview response.')
})
