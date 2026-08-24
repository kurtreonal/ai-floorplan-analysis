/* @vitest-environment jsdom */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { FloorPlanApiError, uploadFloorPlan } from './floorPlans.js'


function successfulResponse(data) {
  return {
    ok: true,
    status: 201,
    json: vi.fn().mockResolvedValue(data),
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('floor plan API client', () => {
  it('sends credentialed multipart data containing only the floor ID and original file', async () => {
    const file = new File([new Uint8Array([1, 2, 3, 4])], 'house-plan.png', {
      type: 'image/png',
    })
    const result = { id: 42, project_floor_id: 12, processing_status: 'uploaded' }
    const fetchMock = vi.fn().mockResolvedValue(successfulResponse(result))
    vi.stubGlobal('fetch', fetchMock)

    await expect(uploadFloorPlan(7, { projectFloorId: 12, file })).resolves.toEqual(result)

    const [url, request] = fetchMock.mock.calls[0]
    expect(url).toBe('http://localhost:8000/api/projects/7/floor-plans')
    expect(request.method).toBe('POST')
    expect(request.credentials).toBe('include')
    expect(request.headers).toEqual({ Accept: 'application/json' })
    expect(request.headers['Content-Type']).toBeUndefined()
    expect(request.body).toBeInstanceOf(FormData)
    expect(Array.from(request.body.keys())).toEqual(['project_floor_id', 'file'])
    expect(request.body.get('project_floor_id')).toBe('12')
    expect(request.body.get('file')).toBe(file)
  })

  it('preserves a sanitized backend status, code, and message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 415,
      json: vi.fn().mockResolvedValue({
        detail: {
          error: {
            code: 'UPLOAD_MIME_EXTENSION_MISMATCH',
            message: 'The file type does not match its extension.',
            details: {},
          },
        },
      }),
    }))

    const error = await uploadFloorPlan(7, {
      projectFloorId: 12,
      file: new File(['data'], 'plan.png', { type: 'image/png' }),
    }).catch((requestError) => requestError)

    expect(error).toBeInstanceOf(FloorPlanApiError)
    expect(error.status).toBe(415)
    expect(error.code).toBe('UPLOAD_MIME_EXTENSION_MISMATCH')
    expect(error.message).toBe('The file type does not match its extension.')
  })

  it('uses a generic safe error for malformed response data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: vi.fn().mockResolvedValue({ raw: '<html>private trace</html>' }),
    }))

    const error = await uploadFloorPlan(7, {
      projectFloorId: 12,
      file: new File(['data'], 'plan.pdf', { type: 'application/pdf' }),
    }).catch((requestError) => requestError)

    expect(error.status).toBe(422)
    expect(error.code).toBeNull()
    expect(error.message).toBe('The floor-plan upload could not be completed.')
    expect(error.message).not.toContain('private trace')
  })

  it('turns network failures into a generic unavailable error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('private network detail')))

    const error = await uploadFloorPlan(7, {
      projectFloorId: 12,
      file: new File(['data'], 'plan.pdf', { type: 'application/pdf' }),
    }).catch((requestError) => requestError)

    expect(error).toBeInstanceOf(FloorPlanApiError)
    expect(error.status).toBe(0)
    expect(error.message).toBe('The floor-plan upload service is temporarily unavailable.')
  })
})
