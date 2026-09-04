/* @vitest-environment jsdom */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { FloorPlanApiError, listFloorPlans, uploadFloorPlan } from './floorPlans.js'


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
  it('lists one project floor with credentials and an abort signal', async () => {
    const payload = [{
      id: 42,
      project_floor_id: 12,
      original_filename: 'house-plan.png',
      mime_type: 'image/png',
      file_size: 4,
      processing_status: 'processed',
    }]
    const fetchMock = vi.fn().mockResolvedValue(successfulResponse(payload))
    vi.stubGlobal('fetch', fetchMock)
    const controller = new AbortController()

    await expect(listFloorPlans(7, {
      projectFloorId: 12,
      signal: controller.signal,
    })).resolves.toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/projects/7/floor-plans?project_floor_id=12',
      {
        method: 'GET',
        credentials: 'include',
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      },
    )
  })

  it('rejects malformed floor-plan collections without retaining private fields', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(successfulResponse([
      { id: '42', storage_path: 'C:\\private\\plan.png' },
    ])))
    const error = await listFloorPlans(7).catch((requestError) => requestError)
    expect(error).toBeInstanceOf(FloorPlanApiError)
    expect(error.message).toBe('The project floor plans could not be loaded.')
    expect(JSON.stringify(error)).not.toContain('private')
  })

  it('preserves safe list authorization errors and aborts', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: vi.fn().mockResolvedValue({
        detail: { error: { code: 'PROJECT_NOT_FOUND', message: 'The requested project was not found.' } },
      }),
    }))
    const error = await listFloorPlans(7).catch((requestError) => requestError)
    expect(error.status).toBe(404)
    expect(error.code).toBe('PROJECT_NOT_FOUND')

    const abortError = new DOMException('Aborted', 'AbortError')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abortError))
    await expect(listFloorPlans(7)).rejects.toBe(abortError)
  })

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
