/* @vitest-environment jsdom */

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  createProject,
  fetchProject,
  listProjects,
  ProjectApiError,
} from './projects.js'


function successfulResponse(data) {
  return {
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(data),
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('project API client', () => {
  it('lists projects with the credentialed cookie flow', async () => {
    const projects = [{ id: 7, status: 'draft' }]
    const fetchMock = vi.fn().mockResolvedValue(successfulResponse(projects))
    vi.stubGlobal('fetch', fetchMock)

    await expect(listProjects()).resolves.toEqual(projects)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/projects',
      expect.objectContaining({
        credentials: 'include',
        headers: { Accept: 'application/json' },
      }),
    )
  })

  it('creates a project using only the approved request fields', async () => {
    const project = { id: 12, name: 'D4 Project', status: 'draft' }
    const fetchMock = vi.fn().mockResolvedValue(successfulResponse(project))
    vi.stubGlobal('fetch', fetchMock)

    await createProject({
      name: 'D4 Project',
      client_name: 'D4 Client',
      location: 'D4 Location',
      owner_id: 999,
      status: 'archived',
    })

    const [url, request] = fetchMock.mock.calls[0]
    expect(url).toBe('http://localhost:8000/api/projects')
    expect(request.method).toBe('POST')
    expect(request.credentials).toBe('include')
    expect(request.headers).toEqual({
      Accept: 'application/json',
      'Content-Type': 'application/json',
    })
    expect(JSON.parse(request.body)).toEqual({
      name: 'D4 Project',
      client_name: 'D4 Client',
      location: 'D4 Location',
    })
  })

  it('loads one project through the D3 endpoint', async () => {
    const project = { id: 31, name: 'Detail', status: 'needs_review' }
    const fetchMock = vi.fn().mockResolvedValue(successfulResponse(project))
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchProject(31)).resolves.toEqual(project)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/projects/31',
      expect.objectContaining({ credentials: 'include' }),
    )
  })

  it('preserves HTTP status without exposing backend response details', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))

    const error = await listProjects().catch((requestError) => requestError)

    expect(error).toBeInstanceOf(ProjectApiError)
    expect(error.status).toBe(503)
    expect(error.message).toBe('The project request could not be completed.')
  })
})
