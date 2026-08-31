/* @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchCurrentLayout, LayoutApiError } from '../../api/layouts.js'
import { fetchReviewImage } from '../../api/reviewImages.js'
import { normalizeCanonicalGeometry } from '../../geometry/canonicalGeometry.js'
import { LayoutEditorPage } from './LayoutEditorPage.jsx'
import fixtureData from '../../../../fixtures/canonical_geometry_v1.json'

vi.mock('../../api/layouts.js', async () => ({
  ...(await vi.importActual('../../api/layouts.js')), fetchCurrentLayout: vi.fn(),
}))
vi.mock('../../api/reviewImages.js', async () => ({
  ...(await vi.importActual('../../api/reviewImages.js')), fetchReviewImage: vi.fn(),
}))
vi.mock('./CanonicalLayoutCanvas.jsx', () => ({
  CanonicalLayoutCanvas: ({ geometry, blueprintImage, visibility }) => (
    <div data-testid="canonical-canvas">
      {geometry.walls.length}/{geometry.rooms.length}/{geometry.symbols.length}/{geometry.routes.length}
      <span>{blueprintImage ? 'blueprint loaded' : 'neutral blueprint'}</span>
      <span>{Object.entries(visibility).map(([key, value]) => `${key}:${value}`).join(',')}</span>
    </div>
  ),
}))

const fixture = fixtureData

function layout(geometry = fixture) {
  return Object.freeze({
    id: 9, project_id: 15, project_floor_id: 2, floor_plan_id: 81,
    version_number: 3, schema_version: 1, is_current: true,
    created_at: '2026-08-31T12:00:00Z', geometry: normalizeCanonicalGeometry(geometry),
  })
}

class LoadedImage {
  naturalWidth = 640
  naturalHeight = 480
  set src(value) { this._src = value; queueMicrotask(() => this.onload?.()) }
}

beforeEach(() => {
  fetchCurrentLayout.mockReset().mockResolvedValue(layout())
  fetchReviewImage.mockReset().mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
  vi.stubGlobal('Image', LoadedImage)
  URL.createObjectURL = vi.fn(() => 'blob:layout')
  URL.revokeObjectURL = vi.fn()
  window.location.hash = '#/app'
})

afterEach(() => {
  cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); window.location.hash = ''
})

describe('layout editor page', () => {
  it('loads canonical geometry and the one safely aligned blueprint with metadata and summary', async () => {
    const view = render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'DESIGNER' } }} />)
    expect(screen.getByRole('status').textContent).toMatch(/Loading/)
    expect(await screen.findByRole('heading', { name: 'Lower Ground Floor 2D layout' })).toBeTruthy()
    expect(fetchCurrentLayout).toHaveBeenCalledWith(15, 2, expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(fetchReviewImage).toHaveBeenCalledWith(81, 103, expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(screen.getByTestId('canonical-canvas').textContent).toContain('1/1/2/1')
    expect(screen.getByText('Project ID').nextSibling.textContent).toBe('15')
    expect(screen.getByText(/Blueprint available/)).toBeTruthy()
    expect(screen.getByRole('link', { name: /Back to project/ }).getAttribute('href')).toBe('#/app/projects/15')
    view.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:layout')
  })

  it('keeps every toggle local, preserves other layers, and announces visibility', async () => {
    render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'DESIGNER' } }} />)
    await screen.findByTestId('canonical-canvas')
    for (const [label, key] of [
      ['Blueprint', 'blueprint'], ['Walls', 'walls'], ['Rooms', 'rooms'],
      ['Symbols', 'symbols'], ['Wiring / conduit', 'routes'],
    ]) {
      const control = screen.getByRole('checkbox', { name: label })
      fireEvent.click(control)
      expect(control.checked).toBe(false)
      expect(screen.getByTestId('canonical-canvas').textContent).toContain(`${key}:false`)
      expect(screen.getByText(`${label} layer hidden.`)).toBeTruthy()
      const other = key === 'walls' ? 'rooms:true' : 'walls:true'
      expect(screen.getByTestId('canonical-canvas').textContent).toContain(other)
      fireEvent.click(control)
      expect(control.checked).toBe(true)
      expect(screen.getByTestId('canonical-canvas').textContent).toContain(`${key}:true`)
    }
    expect(fetchCurrentLayout).toHaveBeenCalledTimes(1)
    expect(fetchReviewImage).toHaveBeenCalledTimes(1)
  })

  it('does not guess missing or mixed provenance and keeps a neutral blueprint', async () => {
    const sourceLess = structuredClone(fixture); sourceLess.walls = []; sourceLess.symbols = []
    fetchCurrentLayout.mockResolvedValueOnce(layout(sourceLess))
    const view = render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'DESIGNER' } }} />)
    expect(await screen.findByText(/missing or mixed/)).toBeTruthy()
    expect(fetchReviewImage).not.toHaveBeenCalled()
    expect(screen.getByTestId('canonical-canvas').textContent).toContain('neutral blueprint')
    view.unmount()
    const mixed = structuredClone(fixture); mixed.symbols[1].processing_job_id = 104
    fetchCurrentLayout.mockResolvedValueOnce(layout(mixed))
    render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'DESIGNER' } }} />)
    expect(await screen.findByText(/missing or mixed/)).toBeTruthy()
    expect(fetchReviewImage).not.toHaveBeenCalled()
  })

  it('sanitizes image decode/dimension failure while retaining canonical geometry', async () => {
    class WrongImage extends LoadedImage { naturalWidth = 639 }
    vi.stubGlobal('Image', WrongImage)
    render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'DESIGNER' } }} />)
    expect(await screen.findByText(/dimensions do not match/)).toBeTruthy()
    expect(screen.getByTestId('canonical-canvas').textContent).toContain('neutral blueprint')
    cleanup()
    class FailedImage extends LoadedImage {
      set src(value) { this._src = value; queueMicrotask(() => this.onerror?.()) }
    }
    vi.stubGlobal('Image', FailedImage)
    render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'DESIGNER' } }} />)
    expect(await screen.findByText(/could not be loaded safely/)).toBeTruthy()
    expect(screen.getByTestId('canonical-canvas').textContent).toContain('neutral blueprint')
  })

  it('handles 401, 404, temporary retry, Admin note, and request abort', async () => {
    fetchCurrentLayout.mockRejectedValueOnce(new LayoutApiError('safe', 404, 'LAYOUT_NOT_FOUND'))
    const missing = render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'DESIGNER' } }} />)
    expect((await screen.findByRole('alert')).textContent).toMatch(/No current layout/)
    missing.unmount()

    fetchCurrentLayout.mockRejectedValueOnce(new LayoutApiError('safe', 503, 'LAYOUT_RETRIEVAL_FAILED')).mockResolvedValueOnce(layout())
    render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'ADMIN' } }} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('Admin read-only view')).toBeTruthy()
    cleanup()

    fetchCurrentLayout.mockRejectedValueOnce(new LayoutApiError('safe', 401, 'AUTHENTICATION_REQUIRED'))
    render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'DESIGNER' } }} />)
    await waitFor(() => expect(window.location.hash).toBe('#/signin?reason=session-expired'))
    cleanup()

    fetchCurrentLayout.mockReturnValueOnce(new Promise(() => {}))
    const pending = render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'DESIGNER' } }} />)
    const signal = fetchCurrentLayout.mock.calls.at(-1)[2].signal
    pending.unmount()
    expect(signal.aborted).toBe(true)
  })
})
