/* @vitest-environment jsdom */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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

it('wires the selected rectangle into the canvas and panel, then freezes redraw on submission', async () => {
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
  const initialSession = canvas.props.regionSession
  fireEvent.click(screen.getByRole('button', { name: 'Select two corners' }))
  expect(canvas.props.tool).toBe('region')
  expect(canvas.props.regionSession).toBe(initialSession + 1)
  expect(typeof canvas.props.onAnalysisRegionChange).toBe('function')
  // The real canvas two-click transform is covered in DrawingRegionCanvas.test;
  // this proves its callback actually reaches page state and the real panel.
  const region = { x: 50, y: 40, width: 300, height: 220 }
  act(() => canvas.props.onAnalysisRegionChange(region))
  expect(canvas.props.analysisRegion).toEqual(region)
  for (const [field, value] of Object.entries(region)) {
    expect(screen.getByLabelText(`Drawing region ${field}`).value).toBe(String(value))
  }
  fireEvent.click(screen.getByRole('checkbox', { name: /Save this draft first/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Process selected drawing' }))
  await waitFor(() => expect(startDrawingRegionProcessing).toHaveBeenCalledTimes(1))
  expect(startDrawingRegionProcessing.mock.calls[0][1].region).toEqual(region)
  expect(canvas.props.tool).toBe('select')
  expect(canvas.props.analysisRegion).toEqual(region)
  expect(screen.getByRole('button', { name: 'Select two corners' }).disabled).toBe(true)
  expect(screen.queryByRole('button', { name: 'Select drawing region' })).toBeNull()
  act(() => canvas.props.onAnalysisRegionChange({ x: 0, y: 0, width: 10, height: 10 }))
  expect(canvas.props.analysisRegion).toEqual(region)
  expect(screen.getByLabelText('Drawing region width').value).toBe('300')
})
