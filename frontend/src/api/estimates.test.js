import { afterEach, expect, it, vi } from 'vitest'
import { createEstimate, EstimateApiError, fetchEstimateOptions, listEstimates } from './estimates.js'

afterEach(() => vi.unstubAllGlobals())
const record = { id: 4, project_id: 15, version_number: 1, currency: 'PHP', total: '120.00', items: [{ line_number: 1, material_id: 5, material_name: 'Test material', material_code: 'M5', unit: 'piece', quantity: '2.0000', captured_unit_price: '60.00', line_total: '120.00' }] }
const respond = (body) => vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => body }))

it('loads project-bound snapshots with credentialed requests and unchanged captured prices', async () => {
  respond([record])
  const controller = new AbortController()
  expect(await listEstimates(15, { signal: controller.signal })).toEqual([record])
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/api/projects/15/estimates'), expect.objectContaining({ credentials: 'include', signal: controller.signal, method: 'GET' }))
})

it('rejects wrong-project and invalid price responses', async () => {
  for (const invalid of [{ ...record, project_id: 16 }, { ...record, total: '-1' }, { ...record, currency: 'INVALID' }, { ...record, items: [{ ...record.items[0], captured_unit_price: null }] }]) {
    respond([invalid])
    await expect(listEstimates(15)).rejects.toMatchObject({ code: 'INVALID_ESTIMATE_RESPONSE' })
  }
})

it('validates readiness and material options instead of inventing defaults', async () => {
  const options = { route_version_id: null, stale: false, floors: [], components: [], materials: [] }
  respond(options)
  expect(await fetchEstimateOptions(15)).toEqual(options)
  respond({ ...options, route_version_id: -2 })
  await expect(fetchEstimateOptions(15)).rejects.toBeInstanceOf(EstimateApiError)
})

it('posts the caller idempotency identity and mappings unchanged', async () => {
  respond(record)
  const payload = { request_id: 'test-identity', route_version_id: 11, components: [], conductor_count: 3 }
  expect(await createEstimate(15, payload)).toEqual(record)
  expect(fetch).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ method: 'POST', body: JSON.stringify(payload), credentials: 'include' }))
})

it('sanitizes server errors and preserves aborts', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({ detail: { error: { code: 'password/private/path' } } }) }))
  await expect(listEstimates(15)).rejects.toMatchObject({ status: 503, code: '', message: 'The estimate request could not be completed.' })
  const abort = new DOMException('aborted', 'AbortError')
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort))
  await expect(listEstimates(15)).rejects.toBe(abort)
  await expect(listEstimates(0)).rejects.toMatchObject({ status: 422 })
})
