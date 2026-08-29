import { API_BASE_URL } from './auth.js'

const GENERIC_ERROR = 'Detection results could not be loaded.'
const WALL_STATUSES = new Set(['detected', 'verified'])
const SYMBOL_STATUSES = new Set(['detected', 'needs_review'])
const REVIEW_DECISIONS = new Set(['confirmed', 'deleted'])

export class DetectionApiError extends Error {
  constructor(message = GENERIC_ERROR, status = 0, code = null) {
    super(message)
    this.name = 'DetectionApiError'
    this.status = status
    this.code = code
  }
}

function positiveId(value) {
  return Number.isSafeInteger(value) && value > 0
}

function finite(value, minimum = 0) {
  return Number.isFinite(value) && value >= minimum
}

function point(value) {
  return value && finite(value.x) && finite(value.y)
}

function validReview(review) {
  if (review === null) return true
  return review && JSON.stringify(Object.keys(review).sort())
    === JSON.stringify(['decision', 'reviewed_at', 'sequence_number'])
    && REVIEW_DECISIONS.has(review.decision)
    && positiveId(review.sequence_number)
    && typeof review.reviewed_at === 'string'
    && Number.isFinite(Date.parse(review.reviewed_at))
}

function validWall(wall, floorPlanId) {
  return wall && positiveId(wall.id) && wall.floor_plan_id === floorPlanId
    && positiveId(wall.processing_job_id) && positiveId(wall.candidate_id)
    && WALL_STATUSES.has(wall.status) && finite(wall.pixels_per_meter, Number.EPSILON)
    && point(wall.raw_pixels?.start) && point(wall.raw_pixels?.end)
    && finite(wall.raw_pixels?.length_pixels)
    && finite(wall.raw_pixels?.angle_degrees)
    && wall.raw_pixels.angle_degrees < 180
    && point(wall.canonical?.start) && point(wall.canonical?.end)
    && finite(wall.canonical?.length_meters)
    && finite(wall.canonical?.angle_degrees)
    && wall.canonical.angle_degrees < 180
}

function validSymbol(symbol, floorPlanId, jobId) {
  const box = symbol?.bounding_box
  const width = symbol?.image_width_pixels
  const height = symbol?.image_height_pixels
  return symbol && positiveId(symbol.id) && symbol.floor_plan_id === floorPlanId
    && symbol.processing_job_id === jobId && positiveId(symbol.prediction_index)
    && symbol.prediction_index <= 300 && SYMBOL_STATUSES.has(symbol.status)
    && Number.isInteger(symbol.original_class?.id) && symbol.original_class.id >= 0
    && typeof symbol.original_class?.name === 'string' && symbol.original_class.name.length > 0
    && finite(symbol.original_confidence) && symbol.original_confidence <= 1
    && finite(symbol.confidence_threshold) && symbol.confidence_threshold <= 1
    && Number.isInteger(width) && width > 0 && width <= 4096
    && Number.isInteger(height) && height > 0 && height <= 4096
    && box && finite(box.x_min) && finite(box.y_min) && finite(box.x_max) && finite(box.y_max)
    && box.x_min <= box.x_max && box.y_min <= box.y_max
    && box.x_max <= width && box.y_max <= height && point(symbol.center)
    && symbol.center.x >= box.x_min && symbol.center.x <= box.x_max
    && symbol.center.y >= box.y_min && symbol.center.y <= box.y_max
    && symbol.maximum_detections === 300
    && typeof symbol.detection_limit_reached === 'boolean'
    && Object.hasOwn(symbol, 'review')
    && validReview(symbol.review)
}

function validate(payload, floorPlanId, jobId) {
  if (!payload || payload.floor_plan_id !== floorPlanId
    || payload.symbol_processing_job_id !== jobId
    || !Array.isArray(payload.walls) || !Array.isArray(payload.symbols)
    || !payload.walls.every((wall) => validWall(wall, floorPlanId))
    || !payload.symbols.every((symbol) => validSymbol(symbol, floorPlanId, jobId))) {
    throw new DetectionApiError()
  }
  if (payload.symbols.length > 1) {
    const [{ image_width_pixels: width, image_height_pixels: height }] = payload.symbols
    if (!payload.symbols.every((symbol) => (
      symbol.image_width_pixels === width && symbol.image_height_pixels === height
    ))) throw new DetectionApiError()
  }
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

export async function fetchDetectionResults(floorPlanId, processingJobId, { signal } = {}) {
  if (!positiveId(floorPlanId) || !positiveId(processingJobId)) throw new DetectionApiError()
  const query = new URLSearchParams({ processing_job_id: String(processingJobId) })
  let response
  try {
    response = await fetch(`${API_BASE_URL}/api/floor-plans/${floorPlanId}/detections?${query}`, {
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new DetectionApiError()
  }
  if (!response.ok) {
    const error = await safeError(response)
    throw new DetectionApiError(error.message, response.status, error.code)
  }
  try {
    return validate(await response.json(), floorPlanId, processingJobId)
  } catch (error) {
    if (error instanceof DetectionApiError) throw error
    throw new DetectionApiError()
  }
}
