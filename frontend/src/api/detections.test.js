import { afterEach, describe, expect, it, vi } from 'vitest'

import { DetectionApiError, fetchDetectionResults } from './detections.js'

function payload() {
  return {
    floor_plan_id: 2,
    symbol_processing_job_id: 3,
    walls: [{
      id: 1, floor_plan_id: 2, processing_job_id: 3, candidate_id: 1,
      status: 'detected', pixels_per_meter: 100,
      raw_pixels: { start: { x: 0, y: 1 }, end: { x: 10, y: 1 }, length_pixels: 10, angle_degrees: 0 },
      canonical: { start: { x: 0, y: 0.01 }, end: { x: 0.1, y: 0.01 }, length_meters: 0.1, angle_degrees: 0 },
    }],
    symbols: [{
      id: 4, floor_plan_id: 2, processing_job_id: 3, prediction_index: 1,
      status: 'needs_review', original_class: { id: 7, name: 'outlet' },
      original_confidence: 0.49, confidence_threshold: 0.5,
      image_width_pixels: 100, image_height_pixels: 80,
      bounding_box: { x_min: 10, y_min: 20, x_max: 30, y_max: 40 },
      center: { x: 20, y: 30 }, maximum_detections: 300,
      detection_limit_reached: false,
    }],
  }
}

afterEach(() => vi.unstubAllGlobals())

describe('detection results API', () => {
  it('uses the exact credentialed version URL and abort signal', async () => {
    const signal = new AbortController().signal
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => payload() })
    vi.stubGlobal('fetch', fetch)
    await expect(fetchDetectionResults(2, 3, { signal })).resolves.toEqual(payload())
    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/floor-plans/2/detections?processing_job_id=3', {
      credentials: 'include', headers: { Accept: 'application/json' }, signal,
    })
  })

  it('rejects malformed, mismatched, and dimension-inconsistent successful data', async () => {
    for (const mutate of [
      (value) => { value.floor_plan_id = 9 },
      (value) => { value.symbols[0].processing_job_id = 8 },
      (value) => { value.symbols[0].bounding_box.x_max = 101 },
      (value) => { value.symbols.push({ ...value.symbols[0], id: 5, image_width_pixels: 101 }) },
    ]) {
      const value = payload(); mutate(value)
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => value }))
      await expect(fetchDetectionResults(2, 3)).rejects.toBeInstanceOf(DetectionApiError)
    }
  })

  it('preserves safe HTTP status/code and abort behavior', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 404,
      json: async () => ({ detail: { error: { code: 'DETECTION_RESULTS_NOT_FOUND', message: 'Not found.' } } }),
    }))
    await expect(fetchDetectionResults(2, 3)).rejects.toMatchObject({ status: 404, code: 'DETECTION_RESULTS_NOT_FOUND' })
    const abort = Object.assign(new Error('aborted'), { name: 'AbortError' })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort))
    await expect(fetchDetectionResults(2, 3)).rejects.toBe(abort)
  })
})
