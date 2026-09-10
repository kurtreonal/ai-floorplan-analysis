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
  DemoInterpretationCanvas: ({ draft, onSelect }) => <div data-testid="demo-canvas">
    {draft.walls.length}/{draft.rooms.length}/{draft.symbols.length}
    <button type="button" onClick={() => onSelect({ kind: 'symbol', id: 'symbol-0001' })}>Select first symbol</button>
  </div>,
}))
vi.mock('./DraftRoomPreview.jsx', () => ({ DraftRoomPreview: ({ draft }) => <div data-testid="draft-3d">{draft.rooms.length} draft rooms</div> }))


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
})
