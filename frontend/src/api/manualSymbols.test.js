import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  createPlacementRequestId,
  ManualSymbolApiError,
  postManualSymbol,
} from './manualSymbols.js'

const requestId = '123e4567-e89b-42d3-a456-426614174000'
const response = {
  id: 4, floor_plan_id: 2, processing_job_id: 3, status: 'manually_added',
  authoritative_class: { id: 7, name: 'outlet' }, center: { x: 20.5, y: 30.25 },
  image_width_pixels: 100, image_height_pixels: 80,
  created_at: '2026-08-30T12:00:00',
}

afterEach(() => vi.unstubAllGlobals())

describe('manual symbols API', () => {
  it('posts the exact credentialed body, URL, and abort signal', async () => {
    const signal = new AbortController().signal
    const fetch = vi.fn().mockResolvedValue({ ok: true, status: 201, json: async () => response })
    vi.stubGlobal('fetch', fetch)
    await expect(postManualSymbol(2, 3, requestId, 9, { x: 20.5, y: 30.25 }, { signal })).resolves.toEqual(response)
    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/floor-plans/2/manual-symbols?processing_job_id=3', {
      method: 'POST', credentials: 'include',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ placement_request_id: requestId, symbol_legend_id: 9, center: { x: 20.5, y: 30.25 } }),
      signal,
    })
  })

  it('validates UUIDs, identifiers, finite coordinates, and strict responses', async () => {
    await expect(postManualSymbol(2, 3, 'bad', 9, { x: 1, y: 2 })).rejects.toBeInstanceOf(ManualSymbolApiError)
    await expect(postManualSymbol(2, 3, requestId, 0, { x: 1, y: 2 })).rejects.toBeInstanceOf(ManualSymbolApiError)
    await expect(postManualSymbol(2, 3, requestId, 9, { x: Number.NaN, y: 2 })).rejects.toBeInstanceOf(ManualSymbolApiError)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ...response, placement_request_id: requestId }) }))
    await expect(postManualSymbol(2, 3, requestId, 9, { x: 1, y: 2 })).rejects.toBeInstanceOf(ManualSymbolApiError)
  })

  it.each([401, 403, 404, 409, 422, 503])('returns a safe %s error', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status,
      json: async () => ({ detail: { error: { code: 'SAFE', message: 'Safe message.' } } }),
    }))
    await expect(postManualSymbol(2, 3, requestId, 9, { x: 1, y: 2 })).rejects.toMatchObject({ status, code: 'SAFE', message: 'Safe message.' })
  })

  it('preserves AbortError and creates a valid fallback UUID', async () => {
    const abort = Object.assign(new Error('aborted'), { name: 'AbortError' })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort))
    await expect(postManualSymbol(2, 3, requestId, 9, { x: 1, y: 2 })).rejects.toBe(abort)
    expect(createPlacementRequestId()).toMatch(/^[0-9a-f-]{36}$/i)
  })
})
