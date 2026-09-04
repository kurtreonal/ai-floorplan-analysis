import { API_BASE_URL } from './auth.js'


const GENERIC_UPLOAD_ERROR = 'The floor-plan upload could not be completed.'
const GENERIC_LIST_ERROR = 'The project floor plans could not be loaded.'


export class FloorPlanApiError extends Error {
  constructor(message, status = 0, code = null) {
    super(message)
    this.name = 'FloorPlanApiError'
    this.status = status
    this.code = code
  }
}

async function parseSafeError(response, genericMessage) {
  try {
    const payload = await response.json()
    const error = payload?.detail?.error
    if (
      typeof error?.code === 'string'
      && error.code.length > 0
      && typeof error?.message === 'string'
      && error.message.length > 0
    ) {
      return { code: error.code, message: error.message }
    }
  } catch {
    // Fall through to the generic safe error.
  }
  return { code: null, message: genericMessage }
}

function normalizeFloorPlan(value) {
  if (
    !Number.isInteger(value?.id)
    || value.id <= 0
    || !Number.isInteger(value?.project_floor_id)
    || value.project_floor_id <= 0
    || typeof value?.original_filename !== 'string'
    || value.original_filename.length === 0
    || typeof value?.mime_type !== 'string'
    || value.mime_type.length === 0
    || !Number.isInteger(value?.file_size)
    || value.file_size < 0
    || typeof value?.processing_status !== 'string'
    || value.processing_status.length === 0
  ) {
    throw new FloorPlanApiError(GENERIC_LIST_ERROR)
  }
  return {
    id: value.id,
    project_floor_id: value.project_floor_id,
    original_filename: value.original_filename,
    mime_type: value.mime_type,
    file_size: value.file_size,
    processing_status: value.processing_status,
  }
}

export async function listFloorPlans(
  projectId,
  { projectFloorId, signal } = {},
) {
  const query = projectFloorId === undefined
    ? ''
    : `?project_floor_id=${encodeURIComponent(projectFloorId)}`
  let response
  try {
    response = await fetch(
      `${API_BASE_URL}/api/projects/${encodeURIComponent(projectId)}/floor-plans${query}`,
      {
        method: 'GET',
        credentials: 'include',
        headers: { Accept: 'application/json' },
        signal,
      },
    )
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new FloorPlanApiError(GENERIC_LIST_ERROR)
  }
  if (!response.ok) {
    const safeError = await parseSafeError(response, GENERIC_LIST_ERROR)
    throw new FloorPlanApiError(safeError.message, response.status, safeError.code)
  }
  const payload = await response.json().catch(() => null)
  if (!Array.isArray(payload)) throw new FloorPlanApiError(GENERIC_LIST_ERROR)
  return payload.map(normalizeFloorPlan)
}

export async function uploadFloorPlan(
  projectId,
  { projectFloorId, file },
  { signal } = {},
) {
  const formData = new FormData()
  formData.append('project_floor_id', String(projectFloorId))
  formData.append('file', file)

  let response
  try {
    response = await fetch(
      `${API_BASE_URL}/api/projects/${encodeURIComponent(projectId)}/floor-plans`,
      {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json' },
        body: formData,
        signal,
      },
    )
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new FloorPlanApiError(
      'The floor-plan upload service is temporarily unavailable.',
    )
  }

  if (!response.ok) {
    const safeError = await parseSafeError(response, GENERIC_UPLOAD_ERROR)
    throw new FloorPlanApiError(
      safeError.message,
      response.status,
      safeError.code,
    )
  }

  return response.json()
}
