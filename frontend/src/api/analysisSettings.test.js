import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchAnalysisSettings, saveFloorElevation, savePageScale } from './analysisSettings.js'

afterEach(() => vi.unstubAllGlobals())

describe('analysis settings transport', () => {
  it('uses credentialed requests and explicit update bodies', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', fetch)
    const signal = new AbortController().signal
    await fetchAnalysisSettings(1, 2, { signal })
    expect(fetch).toHaveBeenLastCalledWith(expect.stringContaining('/api/projects/1/floors/2/analysis-settings'), expect.objectContaining({ method: 'GET', credentials: 'include', signal }))
    const body = { elevation_meters: null, evidence_notes: 'Awaiting survey' }
    await saveFloorElevation(1, 2, body)
    expect(fetch).toHaveBeenLastCalledWith(expect.stringContaining('/elevation'), expect.objectContaining({ method: 'PUT', body: JSON.stringify(body) }))
    await savePageScale(1, 2, 3, { pixels_per_meter: null })
    expect(fetch).toHaveBeenLastCalledWith(expect.stringContaining('/pages/3/scale'), expect.objectContaining({ method: 'PUT' }))
  })

  it('sanitizes failures and preserves abort semantics', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))
    await expect(fetchAnalysisSettings(1, 2)).rejects.toMatchObject({ status: 503 })
    const abort = new DOMException('Aborted', 'AbortError')
    fetch.mockRejectedValue(abort)
    await expect(fetchAnalysisSettings(1, 2)).rejects.toBe(abort)
  })

  it('rejects unsafe path identifiers before networking', async () => {
    vi.stubGlobal('fetch', vi.fn())
    await expect(fetchAnalysisSettings('../1', 2)).rejects.toThrow()
    expect(() => savePageScale(1, 2, 0, {})).toThrow()
    expect(fetch).not.toHaveBeenCalled()
  })
})
