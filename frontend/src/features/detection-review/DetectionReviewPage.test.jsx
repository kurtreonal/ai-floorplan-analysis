/* @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DetectionApiError, fetchDetectionResults } from '../../api/detections.js'
import { DetectionReviewApiError, putDetectionReview } from '../../api/detectionReviews.js'
import { fetchReviewImage, ReviewImageApiError } from '../../api/reviewImages.js'
import { DetectionReviewPage } from './DetectionReviewPage.jsx'

vi.mock('../../api/detections.js', async () => {
  const actual = await vi.importActual('../../api/detections.js')
  return { ...actual, fetchDetectionResults: vi.fn() }
})
vi.mock('../../api/reviewImages.js', async () => {
  const actual = await vi.importActual('../../api/reviewImages.js')
  return { ...actual, fetchReviewImage: vi.fn() }
})
vi.mock('../../api/detectionReviews.js', async () => {
  const actual = await vi.importActual('../../api/detectionReviews.js')
  return { ...actual, putDetectionReview: vi.fn() }
})
vi.mock('./DetectionReviewCanvas.jsx', () => ({
  DetectionReviewCanvas: ({ walls, symbols, onSelect }) => (
    <div data-testid="canvas">{walls.length} walls / {symbols.length} symbols
      {symbols.map((symbol) => <button key={symbol.id} type="button" onClick={() => onSelect(symbol.id)}>Canvas symbol {symbol.id} {symbol.review?.decision || 'pending'}</button>)}
    </div>
  ),
}))

function results({ symbols = true, limit = false } = {}) {
  return {
    floor_plan_id: 2, symbol_processing_job_id: 3,
    walls: [{ id: 1, status: 'detected' }],
    symbols: symbols ? [{
      id: 4, processing_job_id: 3, prediction_index: 1, status: 'needs_review',
      original_class: { id: 7, name: 'outlet' }, original_confidence: 0.49,
      confidence_threshold: 0.5, image_width_pixels: 100, image_height_pixels: 80,
      bounding_box: { x_min: 10, y_min: 20, x_max: 30, y_max: 40 },
      center: { x: 20, y: 30 }, detection_limit_reached: limit,
      review: null,
    }] : [],
  }
}

class LoadedImage {
  naturalWidth = 100
  naturalHeight = 80
  set src(value) { this._src = value; queueMicrotask(() => this.onload?.()) }
}

beforeEach(() => {
  fetchReviewImage.mockReset()
  fetchDetectionResults.mockReset()
  putDetectionReview.mockReset()
  vi.stubGlobal('Image', LoadedImage)
  URL.createObjectURL = vi.fn(() => 'blob:review')
  URL.revokeObjectURL = vi.fn()
  fetchReviewImage.mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
  fetchDetectionResults.mockResolvedValue(results())
  putDetectionReview.mockResolvedValue({
    detected_symbol_id: 4, floor_plan_id: 2, processing_job_id: 3,
    decision: 'confirmed', sequence_number: 1, reviewed_at: '2026-08-29T12:00:00',
  })
  window.location.hash = '#/app'
})

afterEach(() => {
  cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); window.location.hash = ''
})

describe('detection review page', () => {
  it('loads both resources, displays overlays and synchronizes DOM/canvas selection', async () => {
    const view = render(<DetectionReviewPage projectId={1} floorPlanId={2} processingJobId={3} />)
    expect(screen.getByRole('status').textContent).toMatch(/Loading/)
    expect((await screen.findByTestId('canvas')).textContent).toContain('1 walls / 1 symbols')
    fireEvent.click(screen.getByRole('button', { name: 'outlet' }))
    expect(screen.getByText('7 — outlet')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Canvas symbol 4/ }))
    expect(screen.getAllByText('Needs review — below threshold').length).toBeGreaterThan(1)
    expect(screen.queryByText(/drag|move|classification/i)).toBeNull()
    view.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:review')
  })

  it('shows empty results and the detection-cap warning', async () => {
    fetchDetectionResults.mockResolvedValueOnce(results({ symbols: false }))
    render(<DetectionReviewPage projectId={1} floorPlanId={2} processingJobId={3} />)
    expect(await screen.findByText('No persisted detections are available for this processing job.')).toBeTruthy()
    cleanup()
    fetchDetectionResults.mockResolvedValueOnce(results({ limit: true }))
    render(<DetectionReviewPage projectId={1} floorPlanId={2} processingJobId={3} />)
    expect((await screen.findByRole('alert')).textContent).toMatch(/result cap/)
  })

  it('retries temporary errors and safely handles missing images', async () => {
    fetchReviewImage.mockRejectedValueOnce(new ReviewImageApiError('raw', 503, 'REVIEW_IMAGE_UNAVAILABLE'))
    render(<DetectionReviewPage projectId={1} floorPlanId={2} processingJobId={3} />)
    expect((await screen.findByRole('alert')).textContent).toMatch(/temporarily unavailable/)
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByTestId('canvas')).toBeTruthy()
    expect(fetchReviewImage).toHaveBeenCalledTimes(2)
  })

  it('rejects decoded image dimension mismatch without partial rendering', async () => {
    fetchDetectionResults.mockResolvedValueOnce({
      ...results(),
      symbols: [{ ...results().symbols[0], image_width_pixels: 99 }],
    })
    render(<DetectionReviewPage projectId={1} floorPlanId={2} processingJobId={3} />)
    expect((await screen.findByRole('alert')).textContent).toMatch(/could not be loaded safely/)
    expect(screen.queryByTestId('canvas')).toBeNull()
  })

  it('redirects 401 and aborts requests on unmount', async () => {
    fetchDetectionResults.mockRejectedValueOnce(new DetectionApiError('expired', 401, 'AUTHENTICATION_REQUIRED'))
    const view = render(<DetectionReviewPage projectId={1} floorPlanId={2} processingJobId={3} />)
    await waitFor(() => expect(window.location.hash).toBe('#/signin?reason=session-expired'))
    view.unmount()
    const signal = fetchDetectionResults.mock.calls[0][2].signal
    expect(signal.aborted).toBe(true)
  })

  it('confirms, prevents duplicate clicks, updates locally, and preserves selection', async () => {
    let resolveReview
    putDetectionReview.mockReturnValueOnce(new Promise((resolve) => { resolveReview = resolve }))
    render(<DetectionReviewPage projectId={1} floorPlanId={2} processingJobId={3} />)
    await screen.findByTestId('canvas')
    fireEvent.click(screen.getByRole('button', { name: 'outlet' }))
    const confirm = screen.getByRole('button', { name: 'Confirm detection' })
    fireEvent.click(confirm)
    fireEvent.click(confirm)
    expect(putDetectionReview).toHaveBeenCalledTimes(1)
    expect(confirm.disabled).toBe(true)
    resolveReview({
      detected_symbol_id: 4, floor_plan_id: 2, processing_job_id: 3,
      decision: 'confirmed', sequence_number: 1, reviewed_at: '2026-08-29T12:00:00',
    })
    expect(await screen.findByText('Detection confirmed successfully.')).toBeTruthy()
    expect(screen.getAllByText('Confirmed by Designer').length).toBeGreaterThan(0)
    expect(screen.getByText(/7.*outlet/)).toBeTruthy()
    expect(putDetectionReview).toHaveBeenCalledWith(2, 3, 4, 'confirmed')
  })

  it('rejects and reverses while keeping the original result visible', async () => {
    putDetectionReview.mockResolvedValueOnce({
      detected_symbol_id: 4, floor_plan_id: 2, processing_job_id: 3,
      decision: 'deleted', sequence_number: 2, reviewed_at: '2026-08-29T12:01:00',
    }).mockResolvedValueOnce({
      detected_symbol_id: 4, floor_plan_id: 2, processing_job_id: 3,
      decision: 'confirmed', sequence_number: 3, reviewed_at: '2026-08-29T12:02:00',
    })
    render(<DetectionReviewPage projectId={1} floorPlanId={2} processingJobId={3} />)
    await screen.findByTestId('canvas')
    fireEvent.click(screen.getByRole('button', { name: 'outlet' }))
    fireEvent.click(screen.getByRole('button', { name: 'Reject detection' }))
    expect(await screen.findByText(/original AI result remains visible/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /Canvas symbol 4 deleted/ })).toBeTruthy()
    expect(screen.getByText(/7.*outlet/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Confirm detection' }))
    expect(await screen.findByText('Detection confirmed successfully.')).toBeTruthy()
    expect(putDetectionReview).toHaveBeenNthCalledWith(2, 2, 3, 4, 'confirmed')
  })

  it('renders a persisted decision on initial load', async () => {
    const persisted = results()
    persisted.symbols[0].review = {
      decision: 'deleted', sequence_number: 4, reviewed_at: '2026-08-29T12:00:00',
    }
    fetchDetectionResults.mockResolvedValueOnce(persisted)
    render(<DetectionReviewPage projectId={1} floorPlanId={2} processingJobId={3} />)
    expect(await screen.findByRole('button', { name: /Canvas symbol 4 deleted/ })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'outlet' }))
    expect(screen.getAllByText('Rejected by Designer').length).toBeGreaterThan(0)
  })

  it.each([403, 404, 422, 503])('keeps the canvas and offers retry after a safe %s mutation error', async (status) => {
    putDetectionReview.mockRejectedValueOnce(new DetectionReviewApiError('private raw error', status, 'SAFE_CODE'))
    render(<DetectionReviewPage projectId={1} floorPlanId={2} processingJobId={3} />)
    await screen.findByTestId('canvas')
    fireEvent.click(screen.getByRole('button', { name: 'outlet' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm detection' }))
    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.getByTestId('canvas')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Confirm detection' }).disabled).toBe(false)
    expect(screen.queryByText('private raw error')).toBeNull()
  })

  it('redirects a mutation 401 to sign in', async () => {
    putDetectionReview.mockRejectedValueOnce(new DetectionReviewApiError('expired', 401, 'AUTHENTICATION_REQUIRED'))
    render(<DetectionReviewPage projectId={1} floorPlanId={2} processingJobId={3} />)
    await screen.findByTestId('canvas')
    fireEvent.click(screen.getByRole('button', { name: 'outlet' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm detection' }))
    await waitFor(() => expect(window.location.hash).toBe('#/signin?reason=session-expired'))
  })
})
