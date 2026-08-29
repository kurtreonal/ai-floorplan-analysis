import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchReviewImage, ReviewImageApiError } from './reviewImages.js'

afterEach(() => vi.unstubAllGlobals())

describe('review image API', () => {
  it('loads a nonempty PNG blob with credentials and abort signal', async () => {
    const blob = new Blob(['png'], { type: 'image/png' })
    const signal = new AbortController().signal
    const fetch = vi.fn().mockResolvedValue({
      ok: true, headers: new Headers({ 'Content-Type': 'image/png' }), blob: async () => blob,
    })
    vi.stubGlobal('fetch', fetch)
    await expect(fetchReviewImage(2, 3, { signal })).resolves.toBe(blob)
    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/floor-plans/2/review-image?processing_job_id=3', {
      credentials: 'include', headers: { Accept: 'image/png' }, signal,
    })
  })

  it('rejects wrong MIME, empty blobs, and malformed identifiers', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, headers: new Headers({ 'Content-Type': 'text/plain' }),
      blob: async () => new Blob([], { type: 'text/plain' }),
    }))
    await expect(fetchReviewImage(2, 3)).rejects.toBeInstanceOf(ReviewImageApiError)
    await expect(fetchReviewImage(0, 3)).rejects.toBeInstanceOf(ReviewImageApiError)
  })

  it('returns only safe response errors and preserves aborts', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 503,
      json: async () => ({ detail: { error: { code: 'REVIEW_IMAGE_UNAVAILABLE', message: 'Unavailable.' } } }),
    }))
    await expect(fetchReviewImage(2, 3)).rejects.toMatchObject({ status: 503, code: 'REVIEW_IMAGE_UNAVAILABLE' })
    const abort = Object.assign(new Error('aborted'), { name: 'AbortError' })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort))
    await expect(fetchReviewImage(2, 3)).rejects.toBe(abort)
  })
})
