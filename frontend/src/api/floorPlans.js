import { API_BASE_URL } from './auth.js'


const GENERIC_UPLOAD_ERROR = 'The floor-plan upload could not be completed.'


export class FloorPlanApiError extends Error {
  constructor(message, status = 0, code = null) {
    super(message)
    this.name = 'FloorPlanApiError'
    this.status = status
    this.code = code
  }
}

async function parseSafeUploadError(response) {
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
  return { code: null, message: GENERIC_UPLOAD_ERROR }
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
    const safeError = await parseSafeUploadError(response)
    throw new FloorPlanApiError(
      safeError.message,
      response.status,
      safeError.code,
    )
  }

  return response.json()
}
