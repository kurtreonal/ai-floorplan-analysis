/* @vitest-environment jsdom */
import { afterEach, expect, it, vi } from 'vitest'
import { applyProjectPrices, fetchProjectPrice, inspectProjectPrices, listProjectPrices, ProjectPricingError } from './projectPricing.js'
afterEach(() => vi.unstubAllGlobals())
const version = { id: 2, project_id: 15, version_number: 1, filename: 'client.csv' }

it('uses credentialed project endpoints and multipart without setting a broken content-type boundary', async () => {
  const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => version })
  vi.stubGlobal('fetch', fetcher)
  const file = new File(['Name,Unit,Price'], 'client.csv')
  const selection = { request_id: 'id', confirmed: true }
  expect(await applyProjectPrices(15, file, selection)).toEqual(version)
  const [url, options] = fetcher.mock.calls[0]
  expect(url).toBe('http://localhost:8000/api/projects/15/client-pricing/apply')
  expect(options.credentials).toBe('include')
  expect(options.headers).toEqual({ Accept: 'application/json' })
  expect(options.body.get('file').name).toBe('client.csv')
  expect(JSON.parse(options.body.get('selection'))).toEqual(selection)
})

it('rejects cross-project or malformed version responses and hides backend storage details', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => [{ ...version, project_id: 16 }] }))
  await expect(listProjectPrices(15)).rejects.toBeInstanceOf(ProjectPricingError)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({ detail: { error: { message: 'private SQL' } } }) }))
  await expect(listProjectPrices(15)).rejects.not.toHaveProperty('message', 'private SQL')
})

it('keeps sheet/header and estimate comparison scoped to explicit choices', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ sheets: ['Sheet'], columns: [], sheet: 'Sheet' }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ ...version, document: { rows: [] } }) })
  vi.stubGlobal('fetch', fetcher)
  await inspectProjectPrices(15, new File(['x'], 'x.xlsx'), { sheet: 'Sheet', headerRow: 3 })
  expect(fetcher.mock.calls[0][1].body.get('header_row')).toBe('3')
  await fetchProjectPrice(15, 2, { estimateId: 9 })
  expect(fetcher.mock.calls[1][0]).toBe('http://localhost:8000/api/projects/15/client-pricing/2?estimate_id=9')
})
