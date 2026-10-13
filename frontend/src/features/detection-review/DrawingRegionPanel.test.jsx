/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
vi.mock('../../api/processingJobs.js', () => ({ startDrawingRegionProcessing: vi.fn(), fetchProcessingJob: vi.fn() }))
import { fetchProcessingJob, startDrawingRegionProcessing } from '../../api/processingJobs.js'
import { DrawingRegionPanel } from './DrawingRegionPanel.jsx'

const record = { candidate_run_id: 'a'.repeat(32), candidate: { provenance: { source_artifact_sha256: 'b'.repeat(64) },
  payload: { source_plane: { width_pixels: 400, height_pixels: 300 } } } }
const props = { record, region: { x: 50, y: 40, width: 300, height: 220 }, onRegionChange: vi.fn(),
  onSelectRegion: vi.fn(), projectId: 2, projectFloorId: 3, floorPlanId: 7 }
const acknowledgement = () => screen.getByRole('checkbox')
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('drawing-region reprocessing safeguards', () => {
  it('requires acknowledgement and preserves source bounds without editing the draft', async () => {
    startDrawingRegionProcessing.mockResolvedValue({ job_id: 31, status: 'completed' })
    render(<DrawingRegionPanel {...props} />)
    expect(screen.getByRole('button', { name: 'Process selected drawing' }).disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Select two corners' }))
    expect(props.onSelectRegion).toHaveBeenCalledOnce()
    fireEvent.click(acknowledgement())
    fireEvent.click(screen.getByRole('button', { name: 'Process selected drawing' }))
    await screen.findByRole('link', { name: 'Open plan editor' })
    expect(startDrawingRegionProcessing).toHaveBeenCalledWith(7, expect.objectContaining({
      candidate_run_id: record.candidate_run_id, expected_source_artifact_sha256: 'b'.repeat(64), region: props.region,
    }), expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(screen.getByRole('link').getAttribute('href')).toBe('#/app/projects/2/floors/3/floor-plans/7/interpretation/31')
    expect(screen.getByLabelText('Drawing region x').matches(':disabled')).toBe(true)
    expect(props.onRegionChange).not.toHaveBeenCalled()
  })
  it('retries unknown outcomes with identical UUID/rectangle, even if props change', async () => {
    startDrawingRegionProcessing.mockRejectedValueOnce(new Error('network')).mockResolvedValueOnce({ job_id: 31, status: 'completed' })
    const { rerender } = render(<DrawingRegionPanel {...props} />)
    fireEvent.click(acknowledgement())
    fireEvent.click(screen.getByRole('button', { name: 'Process selected drawing' }))
    await screen.findByRole('button', { name: 'Retry identical request' })
    rerender(<DrawingRegionPanel {...props} region={{ x: 10, y: 10, width: 100, height: 100 }} />)
    fireEvent.click(screen.getByRole('button', { name: 'Retry identical request' }))
    await screen.findByRole('link')
    expect(startDrawingRegionProcessing.mock.calls[1][1]).toEqual(startDrawingRegionProcessing.mock.calls[0][1])
    expect(startDrawingRegionProcessing.mock.calls[1][1].region).toEqual(props.region)
  })
  it('polls only the created job and aborts on unmount', async () => {
    startDrawingRegionProcessing.mockResolvedValue({ job_id: 31, status: 'queued' })
    fetchProcessingJob.mockImplementation(() => new Promise(() => {}))
    const { unmount } = render(<DrawingRegionPanel {...props} />)
    fireEvent.click(acknowledgement())
    fireEvent.click(screen.getByRole('button', { name: 'Process selected drawing' }))
    await waitFor(() => expect(fetchProcessingJob).toHaveBeenCalledOnce())
    expect(fetchProcessingJob.mock.calls[0][0]).toBe(31)
    const signal = fetchProcessingJob.mock.calls[0][1].signal
    unmount()
    expect(signal.aborted).toBe(true)
  })
  it('does not adopt a conflicting active job or start an out-of-page rectangle', async () => {
    startDrawingRegionProcessing.mockRejectedValue({ status: 409, existingJobId: 99 })
    const { rerender } = render(<DrawingRegionPanel {...props} region={{ x: 399, y: 0, width: 20, height: 30 }} />)
    fireEvent.click(acknowledgement())
    expect(screen.getByRole('button', { name: 'Process selected drawing' }).disabled).toBe(true)
    rerender(<DrawingRegionPanel {...props} />)
    fireEvent.click(screen.getByRole('button', { name: 'Process selected drawing' }))
    await screen.findByRole('alert')
    expect(screen.getByRole('alert').textContent).toContain('Job #99 is already active. This selection was not started.')
    expect(fetchProcessingJob).not.toHaveBeenCalled()
    expect(screen.queryByRole('link')).toBeNull()
  })
})
