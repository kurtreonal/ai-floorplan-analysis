import { afterEach, describe, expect, it, vi } from 'vitest'
import { ProcessingJobApiError, startDrawingRegionProcessing } from './processingJobs.js'
import { fetchDemoInterpretation } from './demoInterpretation.js'
import { API_BASE_URL } from './auth.js'

const selection = { intent: 'process_drawing_region', candidate_run_id: 'a'.repeat(32),
  expected_source_artifact_sha256: 'b'.repeat(64), region: { x: 100, y: 150, width: 300, height: 220 },
  request_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' }
afterEach(() => vi.restoreAllMocks())

describe('drawing-region job contract', () => {
  it.each(['queued', 'processing', 'completed', 'failed', 'cancelled'])('accepts actual %s replay status without changing request identity', async (status) => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ job_id: 31, status }), { status: 202 }))
    await expect(startDrawingRegionProcessing(7, selection)).resolves.toEqual({ job_id: 31, status })
    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE_URL}/api/floor-plans/7/process`, expect.objectContaining({
      method: 'POST', credentials: 'include', body: JSON.stringify(selection),
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    }))
  })
  it('rejects malformed coordinates/hash/request before sending', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
    for (const bad of [{ ...selection, region: { ...selection.region, x: -1 } },
      { ...selection, expected_source_artifact_sha256: '' }, { ...selection, request_id: 'not-uuid' }]) {
      await expect(startDrawingRegionProcessing(7, bad)).rejects.toBeInstanceOf(ProcessingJobApiError)
    }
    expect(fetchMock).not.toHaveBeenCalled()
  })
  it('loads the exact historical job rather than replacing it with the latest run', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}'))
    await fetchDemoInterpretation(7, { processingJobId: 31 })
    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE_URL}/api/floor-plans/7/interpretation?processing_job_id=31`)
    await expect(fetchDemoInterpretation(7, { processingJobId: 0 })).rejects.toBeInstanceOf(Error)
  })
})
