/* @vitest-environment jsdom */

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  cancelProcessingJob,
  fetchProcessingJob,
  listProcessingJobs,
  ProcessingJobApiError,
  startFloorPlanProcessing,
} from './processingJobs.js'


function response({ ok = true, status = 200, payload }) {
  return {
    ok,
    status,
    json: vi.fn().mockResolvedValue(payload),
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('processing jobs API client', () => {
  it('requests cancellation with the exact credentialed job URL', async () => {
    const payload = { job_id: 31, status: 'processing', cancellation_mode: 'cooperative_requested' }
    const fetchMock = vi.fn().mockResolvedValue(response({ payload }))
    vi.stubGlobal('fetch', fetchMock)
    const signal = new AbortController().signal
    await expect(cancelProcessingJob(31, { signal })).resolves.toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/api/processing-jobs/31/cancel', {
      method: 'POST', credentials: 'include', headers: { Accept: 'application/json' }, signal,
    })
  })

  it('rejects malformed cancellation identities and responses', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    await expect(cancelProcessingJob(0)).rejects.toBeInstanceOf(ProcessingJobApiError)
    expect(fetchMock).not.toHaveBeenCalled()
    fetchMock.mockResolvedValue(response({ payload: { job_id: 32, status: 'cancelled', cancellation_mode: 'queued_cancelled' } }))
    await expect(cancelProcessingJob(31)).rejects.toBeInstanceOf(ProcessingJobApiError)
  })

  it('loads and validates bounded processing-job history', async () => {
    const payload = [{
      job_id: 31,
      type: 'floor_plan_analysis',
      status: 'completed',
      progress: 100,
      error_message: null,
      created_at: '2026-01-02T03:04:05',
      updated_at: '2026-01-02T03:05:05',
    }]
    const fetchMock = vi.fn().mockResolvedValue(response({ payload }))
    vi.stubGlobal('fetch', fetchMock)
    const controller = new AbortController()
    await expect(listProcessingJobs(42, { signal: controller.signal })).resolves.toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/floor-plans/42/processing-jobs?limit=50',
      {
        method: 'GET',
        credentials: 'include',
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      },
    )
  })

  it.each([
    null,
    [{ job_id: 31, type: 'floor_plan_analysis', status: 'completed', progress: 100, error_message: null }],
  ])('rejects malformed history payload %j', async (payload) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ payload })))
    const error = await listProcessingJobs(42).catch((requestError) => requestError)
    expect(error).toBeInstanceOf(ProcessingJobApiError)
    expect(error.message).toBe('Processing-job history could not be loaded.')
  })

  it('starts processing with credentials, JSON acceptance, and no request body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({
      status: 202,
      payload: { job_id: 31, status: 'queued' },
    }))
    vi.stubGlobal('fetch', fetchMock)
    const controller = new AbortController()

    await expect(startFloorPlanProcessing(42, { signal: controller.signal })).resolves.toEqual({
      job_id: 31,
      status: 'queued',
    })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/floor-plans/42/process',
      {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      },
    )
    expect(fetchMock.mock.calls[0][1]).not.toHaveProperty('body')
  })

  it('fetches a processing job with credentials and an abort signal', async () => {
    const payload = {
      job_id: 31,
      type: 'floor_plan_analysis',
      status: 'processing',
      progress: 37,
      error_message: null,
    }
    const fetchMock = vi.fn().mockResolvedValue(response({ payload }))
    vi.stubGlobal('fetch', fetchMock)
    const controller = new AbortController()

    await expect(fetchProcessingJob(31, { signal: controller.signal })).resolves.toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/processing-jobs/31',
      {
        method: 'GET',
        credentials: 'include',
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      },
    )
  })

  it.each(['queued', 'processing', 'completed', 'failed', 'cancelled'])(
    'accepts the %s processing status',
    async (status) => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
        payload: {
          job_id: 31,
          type: 'floor_plan_analysis',
          status,
          progress: status === 'completed' ? 100 : 0,
          error_message: status === 'failed' ? 'Analysis could not be completed.' : null,
        },
      })))

      await expect(fetchProcessingJob(31)).resolves.toMatchObject({ status })
    },
  )

  it('exposes only a valid active-job ID from the structured 409 contract', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
      ok: false,
      status: 409,
      payload: {
        detail: {
          error: {
            code: 'PROCESSING_JOB_ALREADY_ACTIVE',
            message: 'A processing job is already active.',
            details: { job_id: 91, secret: 'do not expose' },
          },
        },
      },
    })))

    const error = await startFloorPlanProcessing(42).catch((requestError) => requestError)

    expect(error).toBeInstanceOf(ProcessingJobApiError)
    expect(error.status).toBe(409)
    expect(error.code).toBe('PROCESSING_JOB_ALREADY_ACTIVE')
    expect(error.existingJobId).toBe(91)
    expect(error).not.toHaveProperty('details')
    expect(JSON.stringify(error)).not.toContain('do not expose')
  })

  it.each([0, -1, 2.5, '91', null])(
    'rejects invalid conflict job ID %s',
    async (jobId) => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
        ok: false,
        status: 409,
        payload: {
          detail: {
            error: {
              code: 'PROCESSING_JOB_ALREADY_ACTIVE',
              message: 'A processing job is already active.',
              details: { job_id: jobId },
            },
          },
        },
      })))

      const error = await startFloorPlanProcessing(42).catch((requestError) => requestError)
      expect(error.existingJobId).toBeNull()
    },
  )

  it('uses a generic error for malformed error data without leaking it', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
      ok: false,
      status: 503,
      payload: { trace: 'C:\\private\\worker.py SQL password=secret' },
    })))

    const error = await fetchProcessingJob(31).catch((requestError) => requestError)

    expect(error.message).toBe('The processing status could not be loaded.')
    expect(error.code).toBeNull()
    expect(JSON.stringify(error)).not.toContain('worker.py')
    expect(JSON.stringify(error)).not.toContain('secret')
  })

  it.each([
    null,
    { job_id: 31, status: 'processing' },
    { job_id: 31, type: 'floor_plan_analysis', status: 'unknown', progress: 3, error_message: null },
    { job_id: 31, type: 'floor_plan_analysis', status: 'processing', progress: 101, error_message: null },
  ])('rejects malformed successful status payloads', async (payload) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ payload })))

    const error = await fetchProcessingJob(31).catch((requestError) => requestError)

    expect(error).toBeInstanceOf(ProcessingJobApiError)
    expect(error.message).toBe('The processing status could not be loaded.')
  })

  it('rejects a malformed successful start payload', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
      status: 202,
      payload: { job_id: '31', status: 'queued', internal_path: 'C:\\private' },
    })))

    const error = await startFloorPlanProcessing(42).catch((requestError) => requestError)
    expect(error.message).toBe('The processing request could not be completed.')
    expect(error.message).not.toContain('private')
  })

  it('turns network details into a generic unavailable error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('socket secret and host path')))

    const error = await fetchProcessingJob(31).catch((requestError) => requestError)
    expect(error).toBeInstanceOf(ProcessingJobApiError)
    expect(error.status).toBe(0)
    expect(error.message).toBe('The processing status could not be loaded.')
    expect(error.message).not.toContain('secret')
  })

  it('preserves abort errors', async () => {
    const abortError = new DOMException('Aborted', 'AbortError')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abortError))

    await expect(fetchProcessingJob(31)).rejects.toBe(abortError)
  })
})
