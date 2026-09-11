import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  DemoInterpretationApiError,
  fetchDemoInterpretation,
  saveDemoLayout,
  saveDemoReview,
} from './demoInterpretation.js'


afterEach(() => vi.restoreAllMocks())


function response(body, { status = 200 } = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}


describe('demo interpretation API', () => {
  it('loads an authenticated floor-plan interpretation', async () => {
    const payload = { candidate_run_id: 'a'.repeat(32) }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(response(payload))
    await expect(fetchDemoInterpretation(7)).resolves.toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/floor-plans/7/interpretation',
      expect.objectContaining({ method: 'GET', credentials: 'include' }),
    )
  })

  it('posts immutable review and canonical save payloads to exact resources', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(response({ review: { revision_number: 1 } }, { status: 201 }))
      .mockResolvedValueOnce(response({ version_number: 1 }, { status: 201 }))
    const review = { candidate_run_id: 'a'.repeat(32), review_complete: false }
    const layout = { candidate_run_id: 'a'.repeat(32), review_revision_number: 1 }

    await saveDemoReview(7, review)
    await saveDemoLayout(2, 3, 7, layout)

    expect(fetchMock.mock.calls[0][0]).toBe('http://localhost:8000/api/floor-plans/7/interpretation/reviews')
    expect(fetchMock.mock.calls[0][1]).toEqual(expect.objectContaining({ method: 'POST', body: JSON.stringify(review) }))
    expect(fetchMock.mock.calls[1][0]).toBe('http://localhost:8000/api/projects/2/floors/3/floor-plans/7/interpretation/layout')
    expect(fetchMock.mock.calls[1][1]).toEqual(expect.objectContaining({ method: 'POST', body: JSON.stringify(layout) }))
  })

  it('preserves only bounded public API errors', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({
      detail: { error: { code: 'SYMBOL_MAPPING_REQUIRED', message: 'Safe message.' } },
    }, { status: 409 }))
    await expect(fetchDemoInterpretation(7)).rejects.toMatchObject({
      name: 'DemoInterpretationApiError', status: 409,
      code: 'SYMBOL_MAPPING_REQUIRED', message: 'Safe message.',
    })
  })

  it('sanitizes network and malformed response failures', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new Error('private path'))
      .mockResolvedValueOnce(new Response('not-json', { status: 200 }))
    await expect(fetchDemoInterpretation(7)).rejects.toBeInstanceOf(DemoInterpretationApiError)
    await expect(fetchDemoInterpretation(7)).rejects.toBeInstanceOf(DemoInterpretationApiError)
  })
})
