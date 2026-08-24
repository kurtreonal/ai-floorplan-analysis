import { API_BASE_URL } from './auth.js'


export class ProjectApiError extends Error {
  constructor(message, status = 0) {
    super(message)
    this.name = 'ProjectApiError'
    this.status = status
  }
}

async function requestProjectJson(path, options = {}) {
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
    if (error.name === 'AbortError') {
      throw error
    }
    throw new ProjectApiError('The project service could not be reached.')
  }

  if (!response.ok) {
    throw new ProjectApiError('The project request could not be completed.', response.status)
  }

  return response.json()
}

export function listProjects({ signal } = {}) {
  return requestProjectJson('/api/projects', { signal })
}

export function createProject(projectData, { signal } = {}) {
  const payload = { name: projectData.name }

  if (projectData.client_name) {
    payload.client_name = projectData.client_name
  }
  if (projectData.location) {
    payload.location = projectData.location
  }

  return requestProjectJson('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
}

export function fetchProject(projectId, { signal } = {}) {
  return requestProjectJson(`/api/projects/${encodeURIComponent(projectId)}`, { signal })
}
