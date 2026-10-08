import { API_BASE_URL } from './auth.js'


const GENERIC_ERROR = 'The demo interpretation operation could not be completed.'


export class DemoInterpretationApiError extends Error {
  constructor(message = GENERIC_ERROR, status = 0, code = null) {
    super(message)
    this.name = 'DemoInterpretationApiError'
    this.status = status
    this.code = code
  }
}


async function request(path, { method = 'GET', body, signal } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new DemoInterpretationApiError()
  }
  if (!response.ok) {
    let error = null
    try {
      error = (await response.json())?.detail?.error
    } catch {
      // Use the bounded public fallback.
    }
    throw new DemoInterpretationApiError(
      typeof error?.message === 'string' ? error.message : GENERIC_ERROR,
      response.status,
      typeof error?.code === 'string' ? error.code : null,
    )
  }
  try {
    return await response.json()
  } catch {
    throw new DemoInterpretationApiError()
  }
}


export function fetchDemoInterpretation(floorPlanId, options = {}) {
  const { processingJobId, ...requestOptions } = options
  if (processingJobId !== undefined && (!Number.isInteger(processingJobId) || processingJobId <= 0)) {
    return Promise.reject(new DemoInterpretationApiError())
  }
  const query = processingJobId === undefined ? '' : `?processing_job_id=${processingJobId}`
  return request(`/api/floor-plans/${floorPlanId}/interpretation${query}`, requestOptions)
}


export function saveDemoReview(floorPlanId, body, options = {}) {
  return request(`/api/floor-plans/${floorPlanId}/interpretation/reviews`, {
    ...options,
    method: 'POST',
    body,
  })
}


export function saveDemoLayout(projectId, floorId, floorPlanId, body, options = {}) {
  return request(
    `/api/projects/${projectId}/floors/${floorId}/floor-plans/${floorPlanId}/interpretation/layout`,
    { ...options, method: 'POST', body },
  )
}
