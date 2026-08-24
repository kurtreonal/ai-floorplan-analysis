/* @vitest-environment jsdom */

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  createProjectFloor,
  listProjectFloors,
  ProjectFloorApiError,
} from './projectFloors.js'


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

describe('project floor API client', () => {
  it('lists floors with a credentialed GET', async () => {
    const floors = [{ id: 12, project_id: 7, name: 'Ground Floor', sort_order: 0 }]
    const fetchMock = vi.fn().mockResolvedValue(successfulResponse(floors))
    vi.stubGlobal('fetch', fetchMock)

    await expect(listProjectFloors(7)).resolves.toEqual(floors)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/projects/7/floors',
      expect.objectContaining({
        credentials: 'include',
        headers: { Accept: 'application/json' },
      }),
    )
    expect(fetchMock.mock.calls[0][1].method).toBeUndefined()
  })

  it('creates a floor using only the approved name field', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(successfulResponse({ id: 12 })))

    await createProjectFloor(7, {
      name: 'Ground Floor',
      id: 999,
      project_id: 44,
      sort_order: 8,
    })

    const [url, request] = fetch.mock.calls[0]
    expect(url).toBe('http://localhost:8000/api/projects/7/floors')
    expect(request.method).toBe('POST')
    expect(request.credentials).toBe('include')
    expect(request.headers).toEqual({
      Accept: 'application/json',
      'Content-Type': 'application/json',
    })
    expect(JSON.parse(request.body)).toEqual({ name: 'Ground Floor' })
  })

  it('preserves response status without exposing raw response bodies', async () => {
    const response = {
      ok: false,
      status: 503,
      json: vi.fn().mockResolvedValue({ private: 'database details' }),
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))

    const error = await listProjectFloors(7).catch((requestError) => requestError)

    expect(error).toBeInstanceOf(ProjectFloorApiError)
    expect(error.status).toBe(503)
    expect(error.message).toBe('The project-floor request could not be completed.')
    expect(response.json).not.toHaveBeenCalled()
  })
})
