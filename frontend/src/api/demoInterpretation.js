import { API_BASE_URL } from './auth.js'


const GENERIC_ERROR = 'VED could not complete this plan request. Please try again.'


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
    throw new DemoInterpretationApiError('Could not reach VED. Keep this page open and try again.')
  }
  if (!response.ok) {
    let error = null, validation = null
    try {
      const result = await response.json()
      error = result?.detail?.error ?? result?.error
      validation = Array.isArray(result?.detail) ? result.detail : null
    } catch {
      // Use the bounded public fallback.
    }
    const invalidWire = validation?.some(item => item.loc?.some?.(key => ['observed_wiring','generated_wiring'].includes(key)))
    const fallback = response.status === 422
      ? invalidWire ? 'A wiring point or connection is invalid. Check the edited path and reconnect its endpoints before saving.'
        : 'A draft setting is invalid. Check the edited item before saving.'
      : response.status === 401 ? 'Your session expired. Sign in again to continue.' : GENERIC_ERROR
    throw new DemoInterpretationApiError(
      typeof error?.message === 'string' ? error.message.slice(0,500) : fallback,
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
