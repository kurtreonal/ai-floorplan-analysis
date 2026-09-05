import { API_BASE_URL } from './auth.js'

export class AnalysisSettingsError extends Error {
  constructor(status = 0) {
    super('Analysis settings could not be loaded or saved. Please retry.')
    this.name = 'AnalysisSettingsError'
    this.status = status
  }
}

async function request(projectId, floorId, suffix, { body, signal } = {}) {
  if (![projectId, floorId].every((id) => Number.isSafeInteger(id) && id > 0)) {
    throw new AnalysisSettingsError()
  }
  let response
  try {
    response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/floors/${floorId}/analysis-settings${suffix}`, {
      method: body === undefined ? 'GET' : 'PUT',
      credentials: 'include', signal,
      headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new AnalysisSettingsError()
  }
  if (!response.ok) throw new AnalysisSettingsError(response.status)
  try {
    return await response.json()
  } catch {
    throw new AnalysisSettingsError()
  }
}

export function fetchAnalysisSettings(projectId, floorId, options) {
  return request(projectId, floorId, '', options)
}

export function saveFloorElevation(projectId, floorId, body, options = {}) {
  return request(projectId, floorId, '/elevation', { ...options, body })
}

export function savePageScale(projectId, floorId, pageId, body, options = {}) {
  if (!Number.isSafeInteger(pageId) || pageId <= 0) throw new AnalysisSettingsError()
  return request(projectId, floorId, `/pages/${pageId}/scale`, { ...options, body })
}
