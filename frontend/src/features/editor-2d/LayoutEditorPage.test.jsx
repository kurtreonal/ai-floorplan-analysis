/* @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchCurrentLayout, LayoutApiError, saveCurrentLayout } from '../../api/layouts.js'
import { fetchReviewImage } from '../../api/reviewImages.js'
import { normalizeCanonicalGeometry } from '../../geometry/canonicalGeometry.js'
import { LayoutEditorPage } from './LayoutEditorPage.jsx'
import fixtureData from '../../../../fixtures/canonical_geometry_v1.json'

vi.mock('../../api/layouts.js', async () => ({
  ...(await vi.importActual('../../api/layouts.js')),
  fetchCurrentLayout: vi.fn(), saveCurrentLayout: vi.fn(),
}))
vi.mock('../../api/reviewImages.js', async () => ({
  ...(await vi.importActual('../../api/reviewImages.js')), fetchReviewImage: vi.fn(),
}))
vi.mock('./CanonicalLayoutCanvas.jsx', () => ({
  CanonicalLayoutCanvas: ({ geometry, blueprintImage, visibility, selectedSymbolId, canEdit, editDisabled, onSelectSymbol, onMoveSymbol }) => (
    <div data-testid="canonical-canvas">
      {geometry.walls.length}/{geometry.rooms.length}/{geometry.symbols.length}/{geometry.routes.length}
      <span>{blueprintImage ? 'blueprint loaded' : 'neutral blueprint'}</span>
      <span>{Object.entries(visibility).map(([key, value]) => `${key}:${value}`).join(',')}</span>
      <span>selected:{selectedSymbolId ?? 'none'},editable:{String(canEdit)},disabled:{String(editDisabled)}</span>
      {geometry.symbols.map((symbol) => (
        <span key={symbol.id}>
          <button type="button" onClick={() => onSelectSymbol(symbol.id)}>Canvas select {symbol.id}</button>
          <button type="button" disabled={!canEdit || editDisabled} onClick={() => onMoveSymbol(symbol.id, { x: 3, y: 2 })}>Canvas move {symbol.id}</button>
        </span>
      ))}
    </div>
  ),
}))

const fixture = fixtureData

function layout(geometry = fixture, versionNumber = 3, id = 9) {
  return Object.freeze({
    id, project_id: 15, project_floor_id: 2, floor_plan_id: 81,
    version_number: versionNumber, schema_version: 1, is_current: true,
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
  saveCurrentLayout.mockReset().mockImplementation(async (projectId, floorId, geometry) => layout(geometry, 4, 10))
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

  it('updates one canonical draft by canvas move, cancels without POST, and detects no-ops', async () => {
    render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'DESIGNER' } }} />)
    await screen.findByTestId('canonical-canvas')
    const save = screen.getByRole('button', { name: 'Save layout' })
    expect(save.disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Canvas move detected:501' }))
    expect(screen.getByText('Unsaved position changes')).toBeTruthy()
    expect(save.disabled).toBe(false)
    expect(screen.getByTestId('canonical-canvas').textContent).toContain('selected:none')
    fireEvent.click(screen.getByRole('button', { name: 'Cancel changes' }))
    expect(screen.getByText('All position changes saved')).toBeTruthy()
    expect(save.disabled).toBe(true)
    expect(saveCurrentLayout).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Canvas select detected:501' }))
    const x = screen.getByLabelText('X position (meters)')
    const y = screen.getByLabelText('Y position (meters)')
    fireEvent.change(x, { target: { value: String(fixture.symbols[0].position.x) } })
    fireEvent.change(y, { target: { value: String(fixture.symbols[0].position.y) } })
    fireEvent.click(screen.getByRole('button', { name: 'Apply position' }))
    expect(save.disabled).toBe(true)
  })

  it('saves the complete keyboard-edited draft once, adopts the server response, and reloads it', async () => {
    const view = render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'DESIGNER' } }} />)
    await screen.findByTestId('canonical-canvas')
    fireEvent.click(screen.getAllByRole('button', { name: 'Select', pressed: false })[0])
    fireEvent.change(screen.getByLabelText('X position (meters)'), { target: { value: '4.25' } })
    fireEvent.change(screen.getByLabelText('Y position (meters)'), { target: { value: '1.75' } })
    fireEvent.click(screen.getByRole('button', { name: 'Apply position' }))
    const save = screen.getByRole('button', { name: 'Save layout' })
    fireEvent.click(save)
    fireEvent.click(save)
    await screen.findByText(/CURRENT CANONICAL LAYOUT · VERSION 4/)
    expect(saveCurrentLayout).toHaveBeenCalledTimes(1)
    const sent = saveCurrentLayout.mock.calls[0][2]
    const options = saveCurrentLayout.mock.calls[0][3]
    expect(options.expectedVersionNumber).toBe(3)
    expect(options.idempotencyKey).toMatch(/^[0-9a-f-]{36}$/)
    expect(Object.keys(sent)).toEqual(Object.keys(fixture))
    expect(sent.symbols[0].position).toEqual({ x: 4.25, y: 1.75 })
    expect(sent.symbols[1]).toEqual(fixture.symbols[1])
    expect(screen.getByText('All position changes saved')).toBeTruthy()

    view.unmount()
    fetchCurrentLayout.mockResolvedValueOnce(layout(sent, 4, 10))
    render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'DESIGNER' } }} />)
    expect(await screen.findByText(/CURRENT CANONICAL LAYOUT · VERSION 4/)).toBeTruthy()
    fireEvent.click(screen.getAllByRole('button', { name: 'Select', pressed: false })[0])
    expect(screen.getByLabelText('X position (meters)').value).toBe('4.25')
    expect(screen.getByLabelText('Y position (meters)').value).toBe('1.75')
  }, 15_000)

  it('retains a failed draft and reconciles an uncertain successful save before retry', async () => {
    render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'DESIGNER' } }} />)
    await screen.findByTestId('canonical-canvas')
    fireEvent.click(screen.getByRole('button', { name: 'Canvas move manual:601' }))
    saveCurrentLayout.mockRejectedValueOnce(new LayoutApiError('safe', 503, 'LAYOUT_SAVE_FAILED'))
    fireEvent.click(screen.getByRole('button', { name: 'Save layout' }))
    expect(await screen.findByRole('button', { name: 'Check server before retry' })).toBeTruthy()
    expect(screen.getByText('Unsaved position changes')).toBeTruthy()
    const draft = saveCurrentLayout.mock.calls[0][2]
    fetchCurrentLayout.mockResolvedValueOnce(layout(draft, 4, 10))
    fireEvent.click(screen.getByRole('button', { name: 'Check server before retry' }))
    expect(await screen.findByText(/CURRENT CANONICAL LAYOUT · VERSION 4/)).toBeTruthy()
    expect(screen.getByText('All position changes saved')).toBeTruthy()
    expect(saveCurrentLayout).toHaveBeenCalledTimes(1)
    expect(fetchCurrentLayout).toHaveBeenCalledTimes(2)
  })

  it('retries an unchanged server with the original expected version and idempotency key', async () => {
    render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'DESIGNER' } }} />)
    await screen.findByTestId('canonical-canvas')
    fireEvent.click(screen.getByRole('button', { name: 'Canvas move manual:601' }))
    saveCurrentLayout.mockRejectedValueOnce(new LayoutApiError('safe', 503, 'LAYOUT_SAVE_FAILED'))
    fireEvent.click(screen.getByRole('button', { name: 'Save layout' }))
    await screen.findByRole('button', { name: 'Check server before retry' })
    const firstOptions = saveCurrentLayout.mock.calls[0][3]
    fetchCurrentLayout.mockResolvedValueOnce(layout())
    fireEvent.click(screen.getByRole('button', { name: 'Check server before retry' }))
    const retry = await screen.findByRole('button', { name: 'Save layout' })
    fireEvent.click(retry)
    await screen.findByText(/CURRENT CANONICAL LAYOUT.*VERSION 4/)
    expect(saveCurrentLayout).toHaveBeenCalledTimes(2)
    expect(saveCurrentLayout.mock.calls[1][3]).toEqual(expect.objectContaining({
      expectedVersionNumber: 3,
      idempotencyKey: firstOptions.idempotencyKey,
    }))
  })

  it('treats deterministic stale and idempotency conflicts as reload-required', async () => {
    render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'DESIGNER' } }} />)
    await screen.findByTestId('canonical-canvas')
    fireEvent.click(screen.getByRole('button', { name: 'Canvas move detected:501' }))
    saveCurrentLayout.mockRejectedValueOnce(new LayoutApiError('safe', 409, 'STALE_LAYOUT_VERSION'))
    fireEvent.click(screen.getByRole('button', { name: 'Save layout' }))
    expect((await screen.findByRole('alert')).textContent).toMatch(/newer layout version/i)
    expect(screen.queryByRole('button', { name: 'Check server before retry' })).toBeNull()
  })

  it('does not overwrite a conflicting server version and makes Admin inspection-only', async () => {
    const designer = render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'DESIGNER' } }} />)
    await screen.findByTestId('canonical-canvas')
    fireEvent.click(screen.getByRole('button', { name: 'Canvas move detected:501' }))
    saveCurrentLayout.mockRejectedValueOnce(new LayoutApiError('safe', 503, 'LAYOUT_SAVE_FAILED'))
    fireEvent.click(screen.getByRole('button', { name: 'Save layout' }))
    await screen.findByRole('button', { name: 'Check server before retry' })
    const different = structuredClone(fixture); different.symbols[1].position = { x: 5, y: 4 }
    fetchCurrentLayout.mockResolvedValueOnce(layout(different, 4, 11))
    fireEvent.click(screen.getByRole('button', { name: 'Check server before retry' }))
    expect((await screen.findByRole('alert')).textContent).toMatch(/different layout version/)
    expect(saveCurrentLayout).toHaveBeenCalledTimes(1)
    designer.unmount()

    render(<LayoutEditorPage projectId={15} projectFloorId={2} session={{ user: { role: 'ADMIN' } }} />)
    await screen.findByTestId('canonical-canvas')
    expect(screen.getByTestId('canonical-canvas').textContent).toContain('editable:false')
    expect(screen.queryByRole('button', { name: 'Save layout' })).toBeNull()
    fireEvent.click(screen.getAllByRole('button', { name: 'Select', pressed: false })[0])
    expect(screen.queryByLabelText('X position (meters)')).toBeNull()
  })
})
