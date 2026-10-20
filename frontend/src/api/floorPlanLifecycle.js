import { API_BASE_URL } from './auth.js'
import { FloorPlanApiError } from './floorPlans.js'

export async function floorPlanLifecycle(projectId, suffix, { method = 'GET', body, signal } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}/api/projects/${encodeURIComponent(projectId)}/${suffix}`, {
      method, credentials: 'include', signal,
      headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new FloorPlanApiError('Floor-plan management is unavailable. Retry your request.')
  }
  if (!response.ok) {
    // Do not display infrastructure details or arbitrary server error bodies.
    const messages = { 401: 'Please sign in again.', 403: 'Only the project Designer can change floor plans.',
      404: 'The floor plan is no longer available.', 409: 'This floor plan changed. Close and reopen these options.' }
    throw new FloorPlanApiError(messages[response.status] || 'The change could not be confirmed. Retry your request.', response.status)
  }
  return response.json()
}
