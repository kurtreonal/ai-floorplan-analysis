import { API_BASE_URL } from './auth.js'

const GENERIC_ERROR = 'The symbol classification correction could not be saved.'

export class DetectionClassificationApiError extends Error {
  constructor(message = GENERIC_ERROR, status = 0, code = null) {
    super(message)
    this.name = 'DetectionClassificationApiError'
    this.status = status
    this.code = code
  }
}

function positiveId(value) {
  return Number.isSafeInteger(value) && value > 0
}

function timestamp(value) {
  return typeof value === 'string' && Number.isFinite(Date.parse(value))
}

function validSnapshot(value) {
  return value
    && JSON.stringify(Object.keys(value).sort())
      === JSON.stringify(['id', 'name', 'symbol_legend_id'])
    && (value.symbol_legend_id === null || positiveId(value.symbol_legend_id))
    && Number.isInteger(value.id)
    && value.id >= 0
    && typeof value.name === 'string'
    && value.name.length > 0
    && value.name.length <= 255
}

function validate(payload, floorPlanId, processingJobId, detectedSymbolId) {
  const expected = [
    'authoritative_class',
    'corrected_at',
    'detected_symbol_id',
    'floor_plan_id',
    'new_class',
    'old_class',
    'processing_job_id',
    'sequence_number',
  ]
  if (!payload
    || JSON.stringify(Object.keys(payload).sort()) !== JSON.stringify(expected)
    || payload.floor_plan_id !== floorPlanId
    || payload.processing_job_id !== processingJobId
    || payload.detected_symbol_id !== detectedSymbolId
    || !validSnapshot(payload.old_class)
    || !validSnapshot(payload.new_class)
    || !validSnapshot(payload.authoritative_class)
    || !(
      (payload.sequence_number === null && payload.corrected_at === null)
      || (positiveId(payload.sequence_number) && timestamp(payload.corrected_at))
    )) throw new DetectionClassificationApiError()
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

export async function putDetectionClassification(
  floorPlanId,
  processingJobId,
  detectedSymbolId,
  symbolLegendId,
  { signal } = {},
) {
  if (!positiveId(floorPlanId) || !positiveId(processingJobId)
    || !positiveId(detectedSymbolId) || !positiveId(symbolLegendId)) {
    throw new DetectionClassificationApiError()
  }
  const query = new URLSearchParams({ processing_job_id: String(processingJobId) })
  let response
  try {
    response = await fetch(
      `${API_BASE_URL}/api/floor-plans/${floorPlanId}/detections/${detectedSymbolId}/classification?${query}`,
      {
        method: 'PUT',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol_legend_id: symbolLegendId }),
        signal,
      },
    )
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new DetectionClassificationApiError()
  }
  if (!response.ok) {
    const error = await safeError(response)
    throw new DetectionClassificationApiError(error.message, response.status, error.code)
  }
  try {
    return validate(
      await response.json(),
      floorPlanId,
      processingJobId,
      detectedSymbolId,
    )
  } catch (error) {
    if (error instanceof DetectionClassificationApiError) throw error
    throw new DetectionClassificationApiError()
  }
}
