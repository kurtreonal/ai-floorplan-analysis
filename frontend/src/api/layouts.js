import { API_BASE_URL } from './auth.js'
import { normalizeCanonicalGeometry } from '../geometry/canonicalGeometry.js'

const GENERIC_ERROR = 'The current layout could not be loaded safely.'
const RESPONSE_KEYS = [
  'id', 'project_id', 'project_floor_id', 'floor_plan_id', 'version_number',
  'schema_version', 'is_current', 'created_at', 'geometry',
]

export class LayoutApiError extends Error {
  constructor(message = GENERIC_ERROR, status = 0, code = null) {
    super(message)
    this.name = 'LayoutApiError'
    this.status = status
    this.code = code
  }
}

function positiveId(value) {
  return Number.isSafeInteger(value) && value > 0
}

function exactObject(value, keys) {
  return value !== null
    && typeof value === 'object'
    && !Array.isArray(value)
    && Object.keys(value).length === keys.length
    && Object.keys(value).every((key) => keys.includes(key))
}

function validateResponse(payload, projectId, projectFloorId) {
  if (!exactObject(payload, RESPONSE_KEYS)
    || !positiveId(payload.id)
    || payload.project_id !== projectId
    || payload.project_floor_id !== projectFloorId
    || !positiveId(payload.floor_plan_id)
    || !positiveId(payload.version_number)
    || payload.schema_version !== 1
    || payload.is_current !== true
    || typeof payload.created_at !== 'string'
    || !Number.isFinite(Date.parse(payload.created_at))) {
    throw new LayoutApiError()
  }

  let geometry
  try {
    geometry = normalizeCanonicalGeometry(payload.geometry)
  } catch {
    throw new LayoutApiError()
  }
  if (geometry.schema_version !== payload.schema_version
    || geometry.project_id !== projectId
    || geometry.floor.project_floor_id !== projectFloorId
    || geometry.floor_plan_id !== payload.floor_plan_id) {
    throw new LayoutApiError()
  }

  return Object.freeze({
    id: payload.id,
    project_id: payload.project_id,
    project_floor_id: payload.project_floor_id,
    floor_plan_id: payload.floor_plan_id,
    version_number: payload.version_number,
    schema_version: payload.schema_version,
    is_current: true,
    created_at: payload.created_at,
    geometry,
  })
}

async function safeError(response) {
  try {
    const error = (await response.json())?.detail?.error
    return typeof error?.code === 'string' && /^[A-Z][A-Z0-9_]{0,63}$/.test(error.code)
      ? error.code
      : null
  } catch {
    return null
  }
}

export async function fetchCurrentLayout(projectId, projectFloorId, { signal } = {}) {
  if (!positiveId(projectId) || !positiveId(projectFloorId)) throw new LayoutApiError()
  let response
  try {
    response = await fetch(
      `${API_BASE_URL}/api/projects/${projectId}/floors/${projectFloorId}/layouts`,
      { credentials: 'include', headers: { Accept: 'application/json' }, signal },
    )
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new LayoutApiError()
  }
  if (!response.ok) {
    throw new LayoutApiError(GENERIC_ERROR, response.status, await safeError(response))
  }
  try {
    return validateResponse(await response.json(), projectId, projectFloorId)
  } catch (error) {
    if (error instanceof LayoutApiError) throw error
    throw new LayoutApiError()
  }
}
