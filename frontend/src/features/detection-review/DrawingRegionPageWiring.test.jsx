/* @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { fetchDemoInterpretation } from '../../api/demoInterpretation.js'
import { fetchReviewImage } from '../../api/reviewImages.js'
import { fetchSymbolLegends } from '../../api/symbolLegends.js'
import { startDrawingRegionProcessing } from '../../api/processingJobs.js'
import { DemoInterpretationPage } from './DemoInterpretationPage.jsx'

const canvas = vi.hoisted(() => ({ props: null }))
vi.mock('./DemoInterpretationCanvas.jsx', () => ({ DemoInterpretationCanvas: (props) => {
  canvas.props = props
  return <div data-testid="drawing-wiring-canvas" />
} }))
vi.mock('../../api/demoInterpretation.js', async () => ({
  ...(await vi.importActual('../../api/demoInterpretation.js')), fetchDemoInterpretation: vi.fn(),
}))
vi.mock('../../api/reviewImages.js', () => ({ fetchReviewImage: vi.fn() }))
vi.mock('../../api/symbolLegends.js', async () => ({
  ...(await vi.importActual('../../api/symbolLegends.js')), fetchSymbolLegends: vi.fn(),
}))
vi.mock('../../api/processingJobs.js', async () => ({
  ...(await vi.importActual('../../api/processingJobs.js')), startDrawingRegionProcessing: vi.fn(),
}))

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.clearAllMocks(); canvas.props = null })

it('automates drawing scope without exposing region selection, reprocessing or gap-repair controls', async () => {
  const record = { candidate_run_id: 'a'.repeat(32), processing_job_id: 4, floor_plan_id: 3,
    floor_plan_page_id: 8, review: null, candidate: {
      provenance: { model_release_id: 'demo_cv_baseline', source_artifact_sha256: 'b'.repeat(64) },
      payload: { source_plane: { width_pixels: 400, height_pixels: 300 },
        walls: { items: [], truncated: false }, rooms: { items: [], truncated: false },
        symbols: { items: [], truncated: false } },
    } }
  fetchDemoInterpretation.mockResolvedValue(record)
  fetchReviewImage.mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
  fetchSymbolLegends.mockResolvedValue([])
  startDrawingRegionProcessing.mockResolvedValue({ job_id: 99, status: 'completed' })
  class LoadedImage {
    naturalWidth = 400
    naturalHeight = 300
    set src(value) { this._src = value; queueMicrotask(() => this.onload?.()) }
  }
  vi.stubGlobal('Image', LoadedImage)
  URL.createObjectURL = vi.fn(() => 'blob:drawing-wiring')
  URL.revokeObjectURL = vi.fn()
  render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
  await screen.findByTestId('drawing-wiring-canvas')
  expect(canvas.props.onAnalysisRegionChange).toBeUndefined()
  expect(canvas.props.analysisRegion).toBeUndefined()
  expect(screen.queryByRole('button', { name: 'Select two corners' })).toBeNull()
  expect(screen.queryByRole('button', { name: 'Process selected drawing' })).toBeNull()
  expect(screen.queryByRole('button', { name: 'Connect walls' })).toBeNull()
  expect(screen.queryByRole('button', { name: 'Select drawing region' })).toBeNull()
  expect(screen.queryByLabelText('Drawing region width')).toBeNull()
  expect(screen.getByRole('button', { name: 'Draw wiring' })).toBeTruthy()
  expect(startDrawingRegionProcessing).not.toHaveBeenCalled()
})
