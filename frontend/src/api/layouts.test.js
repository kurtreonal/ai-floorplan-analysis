import { readFileSync } from 'node:fs'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchCurrentLayout, LayoutApiError, saveCurrentLayout } from './layouts.js'

const fixture = JSON.parse(readFileSync(new URL('../../../fixtures/canonical_geometry_v1.json', import.meta.url), 'utf8'))
const idempotencyKey = '123e4567-e89b-42d3-a456-426614174000'
const saveOptions = { expectedVersionNumber: 2, idempotencyKey }

function response(overrides = {}) {
  return {
    id: 9, project_id: 15, project_floor_id: 2, floor_plan_id: 81,
    version_number: 3, schema_version: 1, is_current: true,
    created_at: '2026-08-31T12:00:00Z', geometry: structuredClone(fixture),
    ...overrides,
  }
}

afterEach(() => vi.unstubAllGlobals())

describe('current layout API', () => {
  it('uses the exact credentialed GET URL, abort signal, and immutable K1 normalization', async () => {
    const signal = new AbortController().signal
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => response() })
    vi.stubGlobal('fetch', fetch)
    const result = await fetchCurrentLayout(15, 2, { signal })
    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/projects/15/floors/2/layouts', {
      credentials: 'include', headers: { Accept: 'application/json' }, signal,
    })
    expect(fetch.mock.calls[0][1].method).toBeUndefined()
    expect(result.geometry).toEqual(fixture)
    expect(result.geometry).not.toBe(fixture)
    expect(Object.isFrozen(result.geometry.symbols[0].position)).toBe(true)
  })

  it('rejects malformed IDs and inconsistent or non-current successful responses', async () => {
    await expect(fetchCurrentLayout(0, 2)).rejects.toBeInstanceOf(LayoutApiError)
    for (const mutate of [
      (value) => { value.project_id = 16 },
      (value) => { value.project_floor_id = 3 },
      (value) => { value.floor_plan_id = 82 },
      (value) => { value.is_current = false },
      (value) => { value.schema_version = 2 },
      (value) => { value.created_at = 'invalid' },
      (value) => { value.geometry.project_id = 16 },
      (value) => { value.geometry.coordinate_system.pixels_per_meter = 0 },
      (value) => { value.internal = 'private' },
    ]) {
      const payload = response(); mutate(payload)
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }))
      await expect(fetchCurrentLayout(15, 2)).rejects.toBeInstanceOf(LayoutApiError)
    }
  })

  it.each([401, 403, 404, 422, 503])('preserves safe status/code for HTTP %s without exposing details', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status,
      json: async () => ({ detail: { error: { code: `SAFE_${status}`, message: 'private SQL path' } } }),
    }))
    await expect(fetchCurrentLayout(15, 2)).rejects.toMatchObject({
      status, code: `SAFE_${status}`, message: 'The current layout could not be loaded safely.',
    })
  })

  it('sanitizes invalid JSON and network failures while preserving aborts', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => { throw new Error('private') } }))
    await expect(fetchCurrentLayout(15, 2)).rejects.toBeInstanceOf(LayoutApiError)
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network private')))
    await expect(fetchCurrentLayout(15, 2)).rejects.toMatchObject({ status: 0 })
    const abort = Object.assign(new Error('aborted'), { name: 'AbortError' })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort))
    await expect(fetchCurrentLayout(15, 2)).rejects.toBe(abort)
  })
})

describe('layout save API', () => {
  it('posts the complete normalized K1 document in the conditional save envelope', async () => {
    const signal = new AbortController().signal
    const input = structuredClone(fixture)
    const original = structuredClone(input)
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => response() })
    vi.stubGlobal('fetch', fetch)

    const result = await saveCurrentLayout(15, 2, input, { ...saveOptions, signal })

    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/projects/15/floors/2/layouts', {
      method: 'POST', credentials: 'include',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({
        expected_version_number: 2,
        idempotency_key: idempotencyKey,
        geometry: fixture,
      }), signal,
    })
    expect(JSON.parse(fetch.mock.calls[0][1].body).geometry).toEqual(fixture)
    expect(input).toEqual(original)
    expect(result.version_number).toBe(3)
    expect(Object.isFrozen(result)).toBe(true)
    expect(Object.isFrozen(result.geometry.symbols[0].position)).toBe(true)
  })

  it('rejects invalid IDs, geometry, and URL/body identity mismatches before fetch', async () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    await expect(saveCurrentLayout(0, 2, fixture, saveOptions)).rejects.toBeInstanceOf(LayoutApiError)
    const wrongProject = structuredClone(fixture); wrongProject.project_id = 16
    await expect(saveCurrentLayout(15, 2, wrongProject, saveOptions)).rejects.toBeInstanceOf(LayoutApiError)
    const wrongFloor = structuredClone(fixture); wrongFloor.floor.project_floor_id = 3
    await expect(saveCurrentLayout(15, 2, wrongFloor, saveOptions)).rejects.toBeInstanceOf(LayoutApiError)
    const malformed = structuredClone(fixture); malformed.symbols[0].position.x = '1'
    await expect(saveCurrentLayout(15, 2, malformed, saveOptions)).rejects.toBeInstanceOf(LayoutApiError)
    await expect(saveCurrentLayout(15, 2, fixture, { ...saveOptions, expectedVersionNumber: 0 })).rejects.toBeInstanceOf(LayoutApiError)
    await expect(saveCurrentLayout(15, 2, fixture, { ...saveOptions, idempotencyKey: 'not-a-uuid' })).rejects.toBeInstanceOf(LayoutApiError)
    expect(fetch).not.toHaveBeenCalled()
  })

  it.each([401, 403, 404, 422, 503])('preserves safe save status/code for HTTP %s', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status,
      json: async () => ({ detail: { error: { code: `SAFE_${status}`, message: 'private SQL path' } } }),
    }))
    await expect(saveCurrentLayout(15, 2, fixture, saveOptions)).rejects.toMatchObject({
      status, code: `SAFE_${status}`, message: 'The layout changes could not be saved safely.',
    })
  })

  it('rejects malformed or mismatched responses, sanitizes networks, and preserves aborts', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => response({ project_id: 16 }) }))
    await expect(saveCurrentLayout(15, 2, fixture, saveOptions)).rejects.toMatchObject({ message: 'The layout changes could not be saved safely.' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => { throw new Error('private body') } }))
    await expect(saveCurrentLayout(15, 2, fixture, saveOptions)).rejects.toMatchObject({ status: 0 })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('private network path')))
    await expect(saveCurrentLayout(15, 2, fixture, saveOptions)).rejects.toMatchObject({ status: 0, message: 'The layout changes could not be saved safely.' })
    const abort = Object.assign(new Error('aborted'), { name: 'AbortError' })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort))
    await expect(saveCurrentLayout(15, 2, fixture, saveOptions)).rejects.toBe(abort)
  })
})
