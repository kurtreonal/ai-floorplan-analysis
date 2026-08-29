import { afterEach, describe, expect, it, vi } from 'vitest'

import { DetectionReviewApiError, putDetectionReview } from './detectionReviews.js'

function response(overrides = {}) {
  return {
    detected_symbol_id: 4,
    floor_plan_id: 2,
    processing_job_id: 3,
    decision: 'confirmed',
    sequence_number: 1,
    reviewed_at: '2026-08-29T12:00:00',
    ...overrides,
  }
}

afterEach(() => vi.unstubAllGlobals())

describe('detection review API', () => {
  it('uses the exact credentialed PUT contract', async () => {
    const signal = new AbortController().signal
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => response() })
    vi.stubGlobal('fetch', fetch)
    await expect(putDetectionReview(2, 3, 4, 'confirmed', { signal })).resolves.toEqual(response())
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/floor-plans/2/detections/4/review?processing_job_id=3',
      {
        method: 'PUT',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: 'confirmed' }),
        signal,
      },
    )
  })

  it('strictly rejects malformed, mismatched, or excessive success responses', async () => {
    for (const payload of [
      response({ detected_symbol_id: 5 }),
      response({ decision: 'corrected' }),
      response({ sequence_number: 0 }),
      response({ reviewed_at: 'not-a-date' }),
      response({ private_path: 'C:\\private' }),
    ]) {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }))
      await expect(putDetectionReview(2, 3, 4, 'confirmed')).rejects.toBeInstanceOf(DetectionReviewApiError)
    }
  })

  it('rejects invalid local inputs and preserves safe HTTP errors', async () => {
    await expect(putDetectionReview(0, 3, 4, 'confirmed')).rejects.toBeInstanceOf(DetectionReviewApiError)
    await expect(putDetectionReview(2, 3, 4, 'corrected')).rejects.toBeInstanceOf(DetectionReviewApiError)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: { error: { code: 'REVIEW_PERSISTENCE_FAILED', message: 'Safe.' } } }),
    }))
    await expect(putDetectionReview(2, 3, 4, 'deleted')).rejects.toMatchObject({
      status: 503,
      code: 'REVIEW_PERSISTENCE_FAILED',
    })
  })
})
