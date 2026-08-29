import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  DetectionClassificationApiError,
  putDetectionClassification,
} from './detectionClassifications.js'

function response(overrides = {}) {
  return {
    detected_symbol_id: 4,
    floor_plan_id: 2,
    processing_job_id: 3,
    sequence_number: 1,
    old_class: { symbol_legend_id: null, id: 7, name: 'outlet' },
    new_class: { symbol_legend_id: 9, id: 2, name: 'Wall outlet' },
    authoritative_class: { symbol_legend_id: 9, id: 2, name: 'Wall outlet' },
    corrected_at: '2026-08-30T12:00:00',
    ...overrides,
  }
}

afterEach(() => vi.unstubAllGlobals())

describe('detection classification API', () => {
  it('uses the exact credentialed PUT contract and abort signal', async () => {
    const signal = new AbortController().signal
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => response() })
    vi.stubGlobal('fetch', fetch)
    await expect(putDetectionClassification(2, 3, 4, 9, { signal })).resolves.toEqual(response())
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/floor-plans/2/detections/4/classification?processing_job_id=3',
      {
        method: 'PUT', credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol_legend_id: 9 }), signal,
      },
    )
  })

  it('accepts the original-class no-op response', async () => {
    const payload = response({
      sequence_number: null,
      new_class: { symbol_legend_id: null, id: 7, name: 'outlet' },
      authoritative_class: { symbol_legend_id: null, id: 7, name: 'outlet' },
      corrected_at: null,
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }))
    await expect(putDetectionClassification(2, 3, 4, 9)).resolves.toEqual(payload)
  })

  it('rejects invalid inputs and malformed, mismatched, or excessive responses', async () => {
    await expect(putDetectionClassification(2, 3, 4, 0)).rejects.toBeInstanceOf(DetectionClassificationApiError)
    for (const payload of [
      response({ detected_symbol_id: 5 }),
      response({ sequence_number: 0 }),
      response({ corrected_at: null }),
      response({ new_class: { symbol_legend_id: 9, id: -1, name: 'Wall outlet' } }),
      response({ private_path: 'C:\\private' }),
    ]) {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }))
      await expect(putDetectionClassification(2, 3, 4, 9)).rejects.toBeInstanceOf(DetectionClassificationApiError)
    }
  })

  it('preserves safe HTTP errors and abort behavior', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 409,
      json: async () => ({ detail: { error: { code: 'SYMBOL_LEGEND_UNAVAILABLE', message: 'Safe.' } } }),
    }))
    await expect(putDetectionClassification(2, 3, 4, 9)).rejects.toMatchObject({
      status: 409, code: 'SYMBOL_LEGEND_UNAVAILABLE',
    })
    const abort = Object.assign(new Error('aborted'), { name: 'AbortError' })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort))
    await expect(putDetectionClassification(2, 3, 4, 9)).rejects.toBe(abort)
  })
})
