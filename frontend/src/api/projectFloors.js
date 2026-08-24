import { API_BASE_URL } from './auth.js'


export class ProjectFloorApiError extends Error {
  constructor(message, status = 0) {
    super(message)
    this.name = 'ProjectFloorApiError'
    this.status = status
  }
}

async function requestProjectFloorJson(path, options = {}) {
  let response
  const { headers, ...requestOptions } = options

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...requestOptions,
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        ...headers,
      },
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ProjectFloorApiError('The project-floor service could not be reached.')
  }

  if (!response.ok) {
    throw new ProjectFloorApiError(
      'The project-floor request could not be completed.',
      response.status,
    )
  }

  return response.json()
}

export function listProjectFloors(projectId, { signal } = {}) {
  return requestProjectFloorJson(
    `/api/projects/${encodeURIComponent(projectId)}/floors`,
    { signal },
  )
}

export function createProjectFloor(projectId, floorData, { signal } = {}) {
  return requestProjectFloorJson(
    `/api/projects/${encodeURIComponent(projectId)}/floors`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: floorData.name }),
      signal,
    },
  )
}
