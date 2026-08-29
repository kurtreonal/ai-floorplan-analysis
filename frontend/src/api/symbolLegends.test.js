import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchSymbolLegends, SymbolLegendApiError } from './symbolLegends.js'

afterEach(() => vi.unstubAllGlobals())

describe('symbol legend API', () => {
  it('loads the exact credentialed active catalog with an abort signal', async () => {
    const signal = new AbortController().signal
    const payload = [{ id: 9, class_id: 2, name: 'Wall outlet' }]
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => payload })
    vi.stubGlobal('fetch', fetch)
    await expect(fetchSymbolLegends({ signal })).resolves.toEqual(payload)
    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/symbol-legends', {
      credentials: 'include', headers: { Accept: 'application/json' }, signal,
    })
  })

  it('accepts an empty catalog and rejects malformed or excessive responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => [] }))
    await expect(fetchSymbolLegends()).resolves.toEqual([])
    for (const payload of [
      {},
      [{ id: 0, class_id: 2, name: 'Outlet' }],
      [{ id: 9, class_id: -1, name: 'Outlet' }],
      [{ id: 9, class_id: 2, name: '' }],
      [{ id: 9, class_id: 2, name: 'Outlet', is_active: true }],
    ]) {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }))
      await expect(fetchSymbolLegends()).rejects.toBeInstanceOf(SymbolLegendApiError)
    }
  })

  it('preserves safe errors and abort behavior', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 503,
      json: async () => ({ detail: { error: { code: 'SYMBOL_LEGENDS_RETRIEVAL_FAILED', message: 'Safe.' } } }),
    }))
    await expect(fetchSymbolLegends()).rejects.toMatchObject({
      status: 503, code: 'SYMBOL_LEGENDS_RETRIEVAL_FAILED',
    })
    const abort = Object.assign(new Error('aborted'), { name: 'AbortError' })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort))
    await expect(fetchSymbolLegends()).rejects.toBe(abort)
  })
})
