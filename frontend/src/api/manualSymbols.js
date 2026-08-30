import { API_BASE_URL } from './auth.js'

const GENERIC_ERROR = 'The manual symbol could not be saved.'
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export class ManualSymbolApiError extends Error {
  constructor(message = GENERIC_ERROR, status = 0, code = null) {
    super(message)
    this.name = 'ManualSymbolApiError'
    this.status = status
    this.code = code
  }
}

function positiveId(value) {
  return Number.isSafeInteger(value) && value > 0
}

function validUuid(value) {
  return typeof value === 'string' && UUID_PATTERN.test(value)
}

function validClass(value) {
  return value
    && JSON.stringify(Object.keys(value).sort()) === JSON.stringify(['id', 'name'])
    && Number.isInteger(value.id) && value.id >= 0
    && typeof value.name === 'string' && value.name.length > 0 && value.name.length <= 255
}

function validPoint(value, width, height) {
  return value && JSON.stringify(Object.keys(value).sort()) === JSON.stringify(['x', 'y'])
    && Number.isFinite(value.x) && Number.isFinite(value.y)
    && value.x >= 0 && value.x <= width && value.y >= 0 && value.y <= height
}

function validate(payload, floorPlanId, processingJobId) {
  const expected = [
    'authoritative_class', 'center', 'created_at', 'floor_plan_id', 'id',
    'image_height_pixels', 'image_width_pixels', 'processing_job_id', 'status',
  ]
  const width = payload?.image_width_pixels
  const height = payload?.image_height_pixels
  if (!payload || JSON.stringify(Object.keys(payload).sort()) !== JSON.stringify(expected)
    || !positiveId(payload.id) || payload.floor_plan_id !== floorPlanId
    || payload.processing_job_id !== processingJobId || payload.status !== 'manually_added'
    || !validClass(payload.authoritative_class)
    || !Number.isInteger(width) || width <= 0 || width > 4096
    || !Number.isInteger(height) || height <= 0 || height > 4096
    || !validPoint(payload.center, width, height)
    || typeof payload.created_at !== 'string'
    || !Number.isFinite(Date.parse(payload.created_at))) throw new ManualSymbolApiError()
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

export function createPlacementRequestId() {
  if (typeof globalThis.crypto?.randomUUID === 'function') return globalThis.crypto.randomUUID()
  if (typeof globalThis.crypto?.getRandomValues !== 'function') throw new ManualSymbolApiError()
  const bytes = new Uint8Array(16)
  globalThis.crypto.getRandomValues(bytes)
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = [...bytes].map((value) => value.toString(16).padStart(2, '0'))
  return `${hex.slice(0, 4).join('')}-${hex.slice(4, 6).join('')}-${hex.slice(6, 8).join('')}-${hex.slice(8, 10).join('')}-${hex.slice(10).join('')}`
}

export async function postManualSymbol(
  floorPlanId,
  processingJobId,
  placementRequestId,
  symbolLegendId,
  center,
  { signal } = {},
) {
  if (!positiveId(floorPlanId) || !positiveId(processingJobId)
    || !positiveId(symbolLegendId) || !validUuid(placementRequestId)
    || !center || !Number.isFinite(center.x) || !Number.isFinite(center.y)
    || center.x < 0 || center.y < 0) throw new ManualSymbolApiError()
  const query = new URLSearchParams({ processing_job_id: String(processingJobId) })
  let response
  try {
    response = await fetch(
      `${API_BASE_URL}/api/floor-plans/${floorPlanId}/manual-symbols?${query}`,
      {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({
          placement_request_id: placementRequestId,
          symbol_legend_id: symbolLegendId,
          center: { x: center.x, y: center.y },
        }),
        signal,
      },
    )
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ManualSymbolApiError()
  }
  if (!response.ok) {
    const error = await safeError(response)
    throw new ManualSymbolApiError(error.message, response.status, error.code)
  }
  try {
    return validate(await response.json(), floorPlanId, processingJobId)
  } catch (error) {
    if (error instanceof ManualSymbolApiError) throw error
    throw new ManualSymbolApiError()
  }
}
