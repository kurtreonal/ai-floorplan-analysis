import { afterEach, expect, it, vi } from 'vitest'
import { previewCircuit } from './routing.js'

afterEach(() => vi.unstubAllGlobals())
const configuration = { circuit_id: 'C-LGT', targets: [{ floor_id: 2, symbol_id: 'detected:1' }] }
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
