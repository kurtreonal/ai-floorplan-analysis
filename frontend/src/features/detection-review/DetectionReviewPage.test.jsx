/* @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DetectionApiError, fetchDetectionResults } from '../../api/detections.js'
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
vi.mock('./DetectionReviewCanvas.jsx', () => ({
  DetectionReviewCanvas: ({ walls, symbols, onSelect }) => (
    <div data-testid="canvas">{walls.length} walls / {symbols.length} symbols
      {symbols.map((symbol) => <button key={symbol.id} type="button" onClick={() => onSelect(symbol.id)}>Canvas symbol {symbol.id}</button>)}
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
    }] : [],
  }
}

class LoadedImage {
  naturalWidth = 100
  naturalHeight = 80
  set src(value) { this._src = value; queueMicrotask(() => this.onload?.()) }
}

beforeEach(() => {
  vi.stubGlobal('Image', LoadedImage)
  URL.createObjectURL = vi.fn(() => 'blob:review')
  URL.revokeObjectURL = vi.fn()
  fetchReviewImage.mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
  fetchDetectionResults.mockResolvedValue(results())
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
    fireEvent.click(screen.getByRole('button', { name: 'Canvas symbol 4' }))
    expect(screen.getAllByText('Needs review — below threshold').length).toBeGreaterThan(1)
    expect(screen.queryByText(/drag|delete|confirm/i)).toBeNull()
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
})
