/* @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchDemoInterpretation, saveDemoLayout, saveDemoReview } from '../../api/demoInterpretation.js'
import { fetchCurrentLayout } from '../../api/layouts.js'
import { fetchReviewImage } from '../../api/reviewImages.js'
import { fetchSymbolLegends } from '../../api/symbolLegends.js'
import { DemoInterpretationPage } from './DemoInterpretationPage.jsx'


vi.mock('../../api/demoInterpretation.js', async () => ({
  ...(await vi.importActual('../../api/demoInterpretation.js')),
  fetchDemoInterpretation: vi.fn(), saveDemoReview: vi.fn(), saveDemoLayout: vi.fn(),
}))
vi.mock('../../api/layouts.js', async () => ({
  ...(await vi.importActual('../../api/layouts.js')), fetchCurrentLayout: vi.fn(),
}))
vi.mock('../../api/reviewImages.js', async () => ({
  ...(await vi.importActual('../../api/reviewImages.js')), fetchReviewImage: vi.fn(),
}))
vi.mock('../../api/symbolLegends.js', async () => ({
  ...(await vi.importActual('../../api/symbolLegends.js')), fetchSymbolLegends: vi.fn(),
}))
vi.mock('./DemoInterpretationCanvas.jsx', () => ({
  DemoInterpretationCanvas: ({ draft, onSelect, onUpdateSymbol }) => <div data-testid="demo-canvas">
    {draft.walls.length}/{draft.rooms.length}/{draft.symbols.length}
    <button type="button" onClick={() => onSelect({ kind: 'symbol', id: 'symbol-0001' })}>Select first symbol</button>
    <button type="button" onClick={() => onUpdateSymbol({ ...draft.symbols[0], center: { x: 85, y: 65 } })}>Drag first symbol</button>
  </div>,
}))
vi.mock('./DraftRoomPreview.jsx', () => ({ DraftRoomPreview: ({ draft, onSelect, onUpdateSymbol }) => <div data-testid="draft-3d">{draft.rooms.length} draft rooms
  <button onClick={() => onSelect({ kind: 'symbol', id: 'symbol-0001' })}>Inspect 3D device</button>
  <button onClick={() => onUpdateSymbol({ ...draft.symbols[0], center: { x: 85, y: 65 } })}>Move 3D device</button>
</div> }))


const record = {
  candidate_run_id: 'a'.repeat(32), processing_job_id: 4, floor_plan_id: 3,
  floor_plan_page_id: 8, review: null,
  candidate: { payload: {
    source_plane: { width_pixels: 400, height_pixels: 300 },
    walls: { truncated: false, items: [{ id: 'wall-0001', start: { x: 10, y: 10 }, end: { x: 100, y: 10 } }] },
    rooms: { truncated: false, items: [{ id: 'room-0001', label: null, boundary: [{ x: 10, y: 10 }, { x: 100, y: 10 }, { x: 100, y: 100 }] }] },
    symbols: { truncated: false, items: [{ id: 'symbol-0001', center: { x: 50, y: 50 } }] },
  } },
}


class LoadedImage {
  naturalWidth = 400
  naturalHeight = 300
  set src(value) { this._src = value; queueMicrotask(() => this.onload?.()) }
}


beforeEach(() => {
  fetchDemoInterpretation.mockReset().mockResolvedValue(structuredClone(record))
  fetchReviewImage.mockReset().mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
  fetchSymbolLegends.mockReset().mockResolvedValue([{ id: 9, class_id: 4, name: 'Approved light' }])
  fetchCurrentLayout.mockReset()
  saveDemoReview.mockReset().mockImplementation(async (_floorPlanId, body) => ({
    ...structuredClone(record),
    review: {
      id: 1, revision_number: 1, reviewed_by_user_id: 2,
      created_at: '2026-09-09T00:00:00Z', ...body,
      symbols: body.symbols.map((symbol) => ({ ...symbol, class_id: 4, class_name: 'Approved light' })),
    },
  }))
  saveDemoLayout.mockReset()
  vi.stubGlobal('Image', LoadedImage)
  URL.createObjectURL = vi.fn(() => 'blob:demo')
  URL.revokeObjectURL = vi.fn()
})


afterEach(() => {
  cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals()
})


describe('unified demo interpretation review', () => {
  it('repairs walls in the shared draft, supports undo, and saves/reloads duplicate tombstones', async () => {
    const source = structuredClone(record)
    source.candidate.payload.walls.items.push(
      { id: 'wall-0002', start: { x: 50, y: 10 }, end: { x: 100, y: 10 } },
      { id: 'wall-0003', start: { x: 50, y: 15 }, end: { x: 50, y: 80 } },
    )
    const original = structuredClone(source)
    fetchDemoInterpretation.mockResolvedValue(source)
    const view = render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByRole('heading', { name: 'Correct floor-plan proposals' })
    fireEvent.click(screen.getByRole('button', { name: 'Connect walls' }))
    expect(screen.getByText(/1 endpoints connected, 1 overlapping segments merged/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await screen.findByText('Review revision 1 saved.')
    expect(saveDemoReview.mock.calls[0][1].walls[1].disposition).toBe('accepted')
    fireEvent.click(screen.getByRole('button', { name: 'Connect walls' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await waitFor(() => expect(saveDemoReview).toHaveBeenCalledTimes(2))
    const body = saveDemoReview.mock.calls[1][1]
    expect(body.walls[1].disposition).toBe('rejected')
    expect(body.walls[2].start).toEqual({ x: 50, y: 10 })
    expect(body.walls).toHaveLength(3)
    expect(body.review_complete).toBe(false)
    const saved = await saveDemoReview.mock.results[1].value
    fetchDemoInterpretation.mockResolvedValue(saved)
    view.unmount()
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByRole('heading', { name: 'Correct floor-plan proposals' })
    fireEvent.click(screen.getByRole('button', { name: 'Connect walls' }))
    expect(screen.getByText(/0 endpoints connected, 0 overlapping segments merged/)).toBeTruthy()
    expect(source).toEqual(original)
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })
  it('keeps names, class corrections, 3D movement, removal and undo in one revisioned draft', async () => {
    const source = structuredClone(record)
    source.candidate.provenance = { model_release_id: 'development_multiclass56_yolo' }
    source.candidate.payload.symbols.items[0].observed_label = 'Troffer light'
    fetchDemoInterpretation.mockResolvedValue(source)
    const view = render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByRole('heading', { name: 'Correct floor-plan proposals' })
    expect(screen.getByRole('complementary', { name: 'Plan editing tools' })).toBeTruthy()
    expect(screen.getByRole('option', { name: /Troffer light · proposal/ })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '3D · Draft preview' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Inspect 3D device' }))
    expect(screen.getByRole('heading', { name: 'Troffer light' })).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Approved VED legend class'), { target: { value: '9' } })
    expect(screen.getByRole('heading', { name: 'Approved light' })).toBeTruthy()
    expect(screen.getByLabelText('Review decision').value).toBe('unresolved')
    fireEvent.click(screen.getByRole('button', { name: 'Move 3D device' }))
    expect(screen.getByLabelText('X').value).toBe('85')
    expect(screen.getByLabelText('Y').value).toBe('65')
    fireEvent.click(screen.getByRole('button', { name: 'Remove device' }))
    expect(screen.getByLabelText('Review decision').value).toBe('rejected')
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
    expect(screen.getByLabelText('Review decision').value).toBe('unresolved')
    fireEvent.click(screen.getByRole('button', { name: 'Redo' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await screen.findByText('Review revision 1 saved.')
    const body = saveDemoReview.mock.calls[0][1]
    expect(body.symbols[0]).toEqual({ id: 'symbol-0001', disposition: 'rejected', center: { x: 85, y: 65 }, symbol_legend_id: 9 })
    expect(body.walls[0]).not.toHaveProperty('estimated_thickness_pixels')
    expect(body.review_complete).toBe(false)
    expect(body.approved_for_layout).toBe(false)
    expect(source.candidate.payload.symbols.items[0].center).toEqual({ x: 50, y: 50 })
    const saved = await saveDemoReview.mock.results[0].value
    fetchDemoInterpretation.mockResolvedValue({ ...saved, candidate: source.candidate })
    view.unmount()
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByRole('heading', { name: 'Correct floor-plan proposals' })
    fireEvent.change(screen.getByLabelText('Select proposal'), { target: { value: 'symbol:symbol-0001' } })
    expect(screen.getByLabelText('Review decision').value).toBe('rejected')
    expect(screen.getByRole('button', { name: 'Remove device' }).disabled).toBe(true)
    expect(screen.getByLabelText('X').value).toBe('85')
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })

  it('preserves untouched extension layers and pending completeness when saving a device draft', async () => {
    const saved = structuredClone(record)
    saved.review = { revision_number: 3, walls: [{ ...record.candidate.payload.walls.items[0], disposition: 'accepted' }], rooms: [],
      symbols: [{ id: 'symbol-0001', disposition: 'unresolved', center: { x: 50, y: 50 }, symbol_legend_id: null }],
      observed_wiring: [{ id: 'wiring-0001', disposition: 'unresolved', points: [{ x: 10, y: 10 }, { x: 50, y: 50 }], completeness: 'partial' }],
      openings: [], panels: [], scale_evidence: [], checklist: { symbols: 'pending', observed_wiring: 'pending' } }
    fetchDemoInterpretation.mockResolvedValue(saved)
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByRole('heading', { name: 'Correct floor-plan proposals' })
    fireEvent.click(screen.getByRole('button', { name: 'Drag first symbol' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await waitFor(() => expect(saveDemoReview).toHaveBeenCalledOnce())
    expect(saveDemoReview.mock.calls[0][1]).toMatchObject({ expected_revision_number: 3, observed_wiring: saved.review.observed_wiring, checklist: saved.review.checklist })
  })
  it('reloads corrected 56-entry proposals from the saved review without changing the AI candidate', async () => {
    const experimental = structuredClone(record)
    experimental.candidate.provenance = { model_release_id: 'development_multiclass56_yolo' }
    fetchDemoInterpretation.mockResolvedValue(experimental)
    const view = render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByText(/includes all 56 eligible drawing-legend entries/i)
    fireEvent.click(screen.getByRole('button', { name: 'Select first symbol' }))
    fireEvent.change(screen.getByLabelText('Review decision'), { target: { value: 'accepted' } })
    fireEvent.change(screen.getByLabelText('Approved VED legend class'), { target: { value: '9' } })
    fireEvent.change(screen.getByLabelText('X'), { target: { value: '75' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await screen.findByText('Review revision 1 saved.')
    const saved = await saveDemoReview.mock.results[0].value
    saved.candidate = structuredClone(experimental.candidate)
    expect(saved.review.symbols[0]).toEqual(expect.objectContaining({
      disposition: 'accepted', symbol_legend_id: 9, center: { x: 75, y: 50 },
    }))
    expect(experimental.candidate.payload.symbols.items[0].center).toEqual({ x: 50, y: 50 })
    fetchDemoInterpretation.mockResolvedValue(saved)
    view.unmount()
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByText(/includes all 56 eligible drawing-legend entries/i)
    fireEvent.click(screen.getByRole('button', { name: 'Select first symbol' }))
    expect(screen.getByLabelText('X').value).toBe('75')
    expect(screen.getByLabelText('Approved VED legend class').value).toBe('9')
    expect(screen.getByLabelText('Review decision').value).toBe('accepted')
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })

  it('previews rooms in 3D with no legend or approval and saves only an unfinished draft', async () => {
    fetchSymbolLegends.mockResolvedValue([])
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByRole('heading', { name: 'Correct floor-plan proposals' })
    fireEvent.click(screen.getByRole('button', { name: '3D · Draft preview' }))
    expect((await screen.findByTestId('draft-3d')).textContent).toContain('1 draft rooms')
    expect(saveDemoLayout).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await waitFor(() => expect(saveDemoReview).toHaveBeenCalledTimes(1))
    expect(saveDemoReview.mock.calls[0][1]).toEqual(expect.objectContaining({ review_complete: false, approved_for_layout: false, wall_height_meters: null }))
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })
  it('loads aligned room wall and symbol proposals with explicit review controls', async () => {
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    expect(await screen.findByRole('heading', { name: 'Correct floor-plan proposals' })).toBeTruthy()
    expect(screen.getByTestId('demo-canvas').textContent).toContain('1/1/1')
    expect(screen.getByText(/Required normalized dimensions: 400 × 300/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Save shared canonical layout' }).disabled).toBe(true)
  })

  it('maps and corrects a symbol then saves a separate immutable review revision', async () => {
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByRole('heading', { name: 'Correct floor-plan proposals' })
    fireEvent.click(screen.getByRole('button', { name: 'Select first symbol' }))
    expect(screen.getByLabelText('Review decision').value).toBe('unresolved')
    fireEvent.change(screen.getByLabelText('Review decision'), { target: { value: 'corrected' } })
    fireEvent.change(screen.getByLabelText('Approved VED legend class'), { target: { value: '9' } })
    fireEvent.change(screen.getByLabelText('Review evidence notes'), { target: { value: 'Reviewed visible geometry.' } })
    fireEvent.click(screen.getByLabelText(/I reviewed every proposed/))
    fireEvent.click(screen.getByRole('button', { name: 'Save review revision' }))

    await waitFor(() => expect(saveDemoReview).toHaveBeenCalledTimes(1))
    expect(saveDemoReview.mock.calls[0][0]).toBe(3)
    expect(saveDemoReview.mock.calls[0][1]).toEqual(expect.objectContaining({
      review_complete: true, approved_for_layout: false,
      symbols: [expect.objectContaining({ id: 'symbol-0001', symbol_legend_id: 9 })],
    }))
    expect(await screen.findByText('Review revision 1 saved.')).toBeTruthy()
  })

  it('keeps experimental template proposals unresolved until a user reviews and saves them', async () => {
    const experimental = structuredClone(record)
    experimental.candidate.provenance = { model_release_id: 'experimental_pull_station_template' }
    fetchDemoInterpretation.mockResolvedValue(experimental)
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByText(/Experimental Pull station template proposals only/)
    fireEvent.click(screen.getByRole('button', { name: 'Select first symbol' }))
    expect(screen.getByLabelText('Review decision').value).toBe('unresolved')
    fireEvent.change(screen.getByLabelText('Review decision'), { target: { value: 'rejected' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await waitFor(() => expect(saveDemoReview).toHaveBeenCalledTimes(1))
    expect(saveDemoReview.mock.calls[0][1].symbols[0].disposition).toBe('rejected')
    expect(saveDemoReview.mock.calls[0][1].review_complete).toBe(false)
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })

  it.each([
    ['experimental_reviewed_symbol_yolo', /narrower model covers troffer/i],
    ['experimental_linked_legend_yolo', /five-class linked-legend model/i],
    ['development_multiclass56_yolo', /includes all 56 eligible drawing-legend entries/i],
  ])('keeps %s symbol proposals unresolved before review', async (provider, note) => {
    const experimental = structuredClone(record)
    experimental.candidate.provenance = { model_release_id: provider }
    fetchDemoInterpretation.mockResolvedValue(experimental)
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByText(note)
    fireEvent.click(screen.getByRole('button', { name: 'Select first symbol' }))
    expect(screen.getByLabelText('Review decision').value).toBe('unresolved')
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await waitFor(() => expect(saveDemoReview).toHaveBeenCalledTimes(1))
    expect(saveDemoReview.mock.calls[0][1].symbols[0].disposition).toBe('unresolved')
    expect(saveDemoReview.mock.calls[0][1].review_complete).toBe(false)
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })
})
