import { API_BASE_URL } from './auth.js'

export class EstimateApiError extends Error {
  constructor(status = 0, code = '') {
    super('The estimate request could not be completed.')
    this.name = 'EstimateApiError'
    this.status = status
    this.code = code
  }
}

const identifier = (value) => Number.isSafeInteger(value) && value > 0
const amount = (value) => (typeof value === 'string' && /^\d+(\.\d+)?$/.test(value)) || (typeof value === 'number' && Number.isFinite(value) && value >= 0)

function validateEstimate(record, projectId) {
  if (!record || !identifier(record.id) || record.project_id !== projectId || !identifier(record.version_number)
    || typeof record.currency !== 'string' || !/^[A-Z]{3}$/.test(record.currency) || !amount(record.total)
    || !Array.isArray(record.items) || record.items.some((item) => !identifier(item.material_id)
      || typeof item.material_name !== 'string' || typeof item.material_code !== 'string' || typeof item.unit !== 'string'
      || ![item.quantity, item.captured_unit_price, item.line_total].every(amount))) {
    throw new EstimateApiError(0, 'INVALID_ESTIMATE_RESPONSE')
  }
  return record
}

async function request(projectId, suffix, { signal, payload } = {}) {
  if (!identifier(projectId)) throw new EstimateApiError(422)
  let response
  try {
    response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/${suffix}`, {
      credentials: 'include', signal, method: payload ? 'POST' : 'GET',
      headers: { Accept: 'application/json', ...(payload ? { 'Content-Type': 'application/json' } : {}) },
      ...(payload ? { body: JSON.stringify(payload) } : {}),
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new EstimateApiError()
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const code = body?.detail?.error?.code
    throw new EstimateApiError(response.status, typeof code === 'string' && /^[A-Z_]+$/.test(code) ? code : '')
  }
  try { return await response.json() } catch { throw new EstimateApiError(0, 'INVALID_ESTIMATE_RESPONSE') }
}

export async function listEstimates(projectId, options) {
  const records = await request(projectId, 'estimates', options)
  if (!Array.isArray(records)) throw new EstimateApiError(0, 'INVALID_ESTIMATE_RESPONSE')
  return records.map((record) => validateEstimate(record, projectId))
}

export async function fetchEstimateOptions(projectId, options) {
  const record = await request(projectId, 'estimate-options', options)
  if (!record || (record.route_version_id !== null && !identifier(record.route_version_id)) || typeof record.stale !== 'boolean'
    || !Array.isArray(record.floors) || !record.floors.every(identifier)
    || !Array.isArray(record.components) || record.components.some((item) => !Number.isSafeInteger(item.class_id) || item.class_id < 0 || typeof item.class_name !== 'string' || !amount(item.quantity))
    || !Array.isArray(record.materials) || record.materials.some((item) => !identifier(item.id) || typeof item.name !== 'string' || typeof item.unit !== 'string' || typeof item.has_price !== 'boolean')) {
    throw new EstimateApiError(0, 'INVALID_ESTIMATE_RESPONSE')
  }
  return record
}

export async function createEstimate(projectId, payload, options) {
  return validateEstimate(await request(projectId, 'estimates', { ...options, payload }), projectId)
}
