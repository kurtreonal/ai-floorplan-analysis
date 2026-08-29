import { API_BASE_URL } from './auth.js'

const GENERIC_ERROR = 'The aligned blueprint reference could not be loaded.'

export class ReviewImageApiError extends Error {
  constructor(message = GENERIC_ERROR, status = 0, code = null) {
    super(message)
    this.name = 'ReviewImageApiError'
    this.status = status
    this.code = code
  }
}

function positiveId(value) {
  return Number.isSafeInteger(value) && value > 0
}

async function safeError(response) {
  try {
    const error = (await response.json())?.detail?.error
    return {
      code: typeof error?.code === 'string' ? error.code : null,
      message: typeof error?.message === 'string' ? error.message : GENERIC_ERROR,
    }
  } catch {
    return { code: null, message: GENERIC_ERROR }
  }
}

export async function fetchReviewImage(floorPlanId, processingJobId, { signal } = {}) {
  if (!positiveId(floorPlanId) || !positiveId(processingJobId)) throw new ReviewImageApiError()
  const query = new URLSearchParams({ processing_job_id: String(processingJobId) })
  let response
  try {
    response = await fetch(`${API_BASE_URL}/api/floor-plans/${floorPlanId}/review-image?${query}`, {
      credentials: 'include',
      headers: { Accept: 'image/png' },
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ReviewImageApiError()
  }
  if (!response.ok) {
    const error = await safeError(response)
    throw new ReviewImageApiError(error.message, response.status, error.code)
  }
  const contentType = response.headers.get('content-type')?.split(';')[0].trim().toLowerCase()
  if (contentType !== 'image/png') throw new ReviewImageApiError()
  const blob = await response.blob()
  if (!(blob instanceof Blob) || blob.size <= 0 || blob.type.split(';')[0] !== 'image/png') {
    throw new ReviewImageApiError()
  }
  return blob
}
