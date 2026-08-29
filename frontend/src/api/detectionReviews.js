import { API_BASE_URL } from './auth.js'

const GENERIC_ERROR = 'The detection review could not be saved.'
const DECISIONS = new Set(['confirmed', 'deleted'])

export class DetectionReviewApiError extends Error {
  constructor(message = GENERIC_ERROR, status = 0, code = null) {
    super(message)
    this.name = 'DetectionReviewApiError'
    this.status = status
    this.code = code
  }
}

function positiveId(value) {
  return Number.isSafeInteger(value) && value > 0
}

function timestamp(value) {
  return typeof value === 'string' && value.length > 0 && Number.isFinite(Date.parse(value))
}

function validate(payload, floorPlanId, processingJobId, detectedSymbolId) {
  const keys = payload && Object.keys(payload).sort()
  const expected = [
    'decision',
    'detected_symbol_id',
    'floor_plan_id',
    'processing_job_id',
    'reviewed_at',
    'sequence_number',
  ]
  if (!payload || JSON.stringify(keys) !== JSON.stringify(expected)
    || payload.floor_plan_id !== floorPlanId
    || payload.processing_job_id !== processingJobId
    || payload.detected_symbol_id !== detectedSymbolId
    || !DECISIONS.has(payload.decision)
    || !positiveId(payload.sequence_number)
    || !timestamp(payload.reviewed_at)) throw new DetectionReviewApiError()
  return payload
}

async function safeError(response) {
  try {
    const payload = await response.json()
    const error = payload?.detail?.error
    return {
      code: typeof error?.code === 'string' ? error.code : null,
      message: typeof error?.message === 'string' ? error.message : GENERIC_ERROR,
    }
  } catch {
    return { code: null, message: GENERIC_ERROR }
  }
}

export async function putDetectionReview(
  floorPlanId,
  processingJobId,
  detectedSymbolId,
  decision,
  { signal } = {},
) {
  if (!positiveId(floorPlanId) || !positiveId(processingJobId)
    || !positiveId(detectedSymbolId) || !DECISIONS.has(decision)) {
    throw new DetectionReviewApiError()
  }
  const query = new URLSearchParams({ processing_job_id: String(processingJobId) })
  let response
  try {
    response = await fetch(
      `${API_BASE_URL}/api/floor-plans/${floorPlanId}/detections/${detectedSymbolId}/review?${query}`,
      {
        method: 'PUT',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision }),
        signal,
      },
    )
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new DetectionReviewApiError()
  }
  if (!response.ok) {
    const error = await safeError(response)
    throw new DetectionReviewApiError(error.message, response.status, error.code)
  }
  try {
    return validate(await response.json(), floorPlanId, processingJobId, detectedSymbolId)
  } catch (error) {
    if (error instanceof DetectionReviewApiError) throw error
    throw new DetectionReviewApiError()
  }
}
