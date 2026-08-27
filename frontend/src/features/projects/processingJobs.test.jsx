/* @vitest-environment jsdom */

import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  fetchProcessingJob,
  ProcessingJobApiError,
  startFloorPlanProcessing,
} from '../../api/processingJobs.js'
import {
  PROCESSING_POLL_INTERVAL_MS,
  ProcessingJobPanel,
} from './ProcessingJobPanel.jsx'


vi.mock('../../api/processingJobs.js', async () => {
  const actual = await vi.importActual('../../api/processingJobs.js')
  return {
    ...actual,
    fetchProcessingJob: vi.fn(),
    startFloorPlanProcessing: vi.fn(),
  }
})

const FLOOR_PLAN_ID = 42
const JOB_ID = 31

function job(status, progress = 0, errorMessage = null) {
  return {
    job_id: JOB_ID,
    type: 'floor_plan_analysis',
    status,
    progress,
    error_message: errorMessage,
  }
}

function renderPanel() {
  return render(
    <ProcessingJobPanel
      floorPlanId={FLOOR_PLAN_ID}
      originalFilename="house-plan.png"
    />,
  )
}

async function settle() {
  await act(async () => {})
}

async function startJob() {
  startFloorPlanProcessing.mockResolvedValueOnce({ job_id: JOB_ID, status: 'queued' })
  fireEvent.click(screen.getByRole('button', { name: 'Start processing' }))
  await settle()
}

async function runNextPoll() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(PROCESSING_POLL_INTERVAL_MS)
  })
}

beforeEach(() => {
  window.location.hash = ''
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.useRealTimers()
  window.location.hash = ''
})

describe('processing job panel', () => {
  it('shows the ready state and start action', () => {
    renderPanel()
    expect(screen.getByText(/Ready to create a processing job/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Start processing' })).toBeTruthy()
  })

  it('uses the original filename in its accessible label', () => {
    renderPanel()
    expect(screen.getByRole('region', { name: 'Processing controls for house-plan.png' })).toBeTruthy()
  })

  it('starts only the trusted floor-plan ID with an abort signal', async () => {
    renderPanel()
    await startJob()

    expect(startFloorPlanProcessing).toHaveBeenCalledWith(
      FLOOR_PLAN_ID,
      { signal: expect.any(AbortSignal) },
    )
  })

  it('locks repeated starts while the request is pending', async () => {
    let resolveStart
    startFloorPlanProcessing.mockReturnValue(new Promise((resolve) => {
      resolveStart = resolve
    }))
    renderPanel()
    const startButton = screen.getByRole('button', { name: 'Start processing' })

    fireEvent.click(startButton)
    fireEvent.click(startButton)

    expect(screen.getByRole('button', { name: 'Starting…' }).disabled).toBe(true)
    expect(startFloorPlanProcessing).toHaveBeenCalledTimes(1)
    await act(async () => resolveStart({ job_id: JOB_ID, status: 'queued' }))
  })

  it('shows a queued job with backend progress and its ID', async () => {
    renderPanel()
    await startJob()

    expect(screen.getByText('Queued')).toBeTruthy()
    expect(screen.getAllByText('0%')).toHaveLength(2)
    expect(screen.getByText('JOB #31')).toBeTruthy()
    expect(screen.getByRole('progressbar').value).toBe(0)
  })

  it('waits for the configured interval before the first status request', async () => {
    vi.useFakeTimers()
    renderPanel()
    await startJob()

    await act(async () => vi.advanceTimersByTimeAsync(PROCESSING_POLL_INTERVAL_MS - 1))
    expect(fetchProcessingJob).not.toHaveBeenCalled()
  })

  it('polls the queued job after the configured interval', async () => {
    vi.useFakeTimers()
    fetchProcessingJob.mockResolvedValueOnce(job('queued', 0))
    renderPanel()
    await startJob()
    await runNextPoll()

    expect(fetchProcessingJob).toHaveBeenCalledWith(
      JOB_ID,
      { signal: expect.any(AbortSignal) },
    )
  })

  it('renders the exact backend processing progress', async () => {
    vi.useFakeTimers()
    fetchProcessingJob.mockResolvedValueOnce(job('processing', 37))
    renderPanel()
    await startJob()
    await runNextPoll()

    expect(screen.getByText('Processing')).toBeTruthy()
    expect(screen.getAllByText('37%')).toHaveLength(2)
    expect(screen.getByRole('progressbar').value).toBe(37)
  })

  it('does not infer progress between status responses', async () => {
    vi.useFakeTimers()
    fetchProcessingJob.mockResolvedValueOnce(job('processing', 18))
    renderPanel()
    await startJob()
    await runNextPoll()
    await act(async () => vi.advanceTimersByTimeAsync(PROCESSING_POLL_INTERVAL_MS - 1))

    expect(screen.getAllByText('18%')).toHaveLength(2)
    expect(fetchProcessingJob).toHaveBeenCalledTimes(1)
  })

  it('never overlaps status requests', async () => {
    vi.useFakeTimers()
    fetchProcessingJob.mockReturnValue(new Promise(() => {}))
    renderPanel()
    await startJob()
    await runNextPoll()
    await act(async () => vi.advanceTimersByTimeAsync(PROCESSING_POLL_INTERVAL_MS * 5))

    expect(fetchProcessingJob).toHaveBeenCalledTimes(1)
  })

  it('shows completed and stops polling', async () => {
    vi.useFakeTimers()
    fetchProcessingJob.mockResolvedValueOnce(job('completed', 100))
    renderPanel()
    await startJob()
    await runNextPoll()
    await act(async () => vi.advanceTimersByTimeAsync(PROCESSING_POLL_INTERVAL_MS * 3))

    expect(screen.getByText('Processing completed.')).toBeTruthy()
    expect(fetchProcessingJob).toHaveBeenCalledTimes(1)
  })

  it('explains that completed analysis review is a later feature', async () => {
    vi.useFakeTimers()
    fetchProcessingJob.mockResolvedValueOnce(job('completed', 100))
    renderPanel()
    await startJob()
    await runNextPoll()

    expect(screen.getByText(/Analysis review and results will be available in a later feature/)).toBeTruthy()
  })

  it('shows only the sanitized failed-job message', async () => {
    vi.useFakeTimers()
    fetchProcessingJob.mockResolvedValueOnce(job('failed', 62, 'Analysis could not be completed.'))
    renderPanel()
    await startJob()
    await runNextPoll()

    expect(screen.getByText('Analysis could not be completed.')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Retry processing' })).toBeTruthy()
  })

  it('uses a generic failed message when the backend supplies none', async () => {
    vi.useFakeTimers()
    fetchProcessingJob.mockResolvedValueOnce(job('failed', 62, null))
    renderPanel()
    await startJob()
    await runNextPoll()

    expect(screen.getByText(/failed without a public error message/)).toBeTruthy()
  })

  it('starts a new job when failed processing is retried', async () => {
    vi.useFakeTimers()
    fetchProcessingJob.mockResolvedValueOnce(job('failed', 62, null))
    renderPanel()
    await startJob()
    await runNextPoll()
    startFloorPlanProcessing.mockResolvedValueOnce({ job_id: 47, status: 'queued' })

    fireEvent.click(screen.getByRole('button', { name: 'Retry processing' }))
    await settle()

    expect(startFloorPlanProcessing).toHaveBeenCalledTimes(2)
    expect(screen.getByText('JOB #47')).toBeTruthy()
  })

  it('shows cancellation as a neutral terminal state', async () => {
    vi.useFakeTimers()
    fetchProcessingJob.mockResolvedValueOnce(job('cancelled', 24))
    renderPanel()
    await startJob()
    await runNextPoll()

    expect(screen.getByText('Processing was cancelled.')).toBeTruthy()
    expect(screen.getByText('You can start a new processing attempt.')).toBeTruthy()
  })

  it('starts a new job from the cancelled state', async () => {
    vi.useFakeTimers()
    fetchProcessingJob.mockResolvedValueOnce(job('cancelled', 24))
    renderPanel()
    await startJob()
    await runNextPoll()
    startFloorPlanProcessing.mockResolvedValueOnce({ job_id: 48, status: 'queued' })

    fireEvent.click(screen.getByRole('button', { name: 'Start new attempt' }))
    await settle()

    expect(startFloorPlanProcessing).toHaveBeenCalledTimes(2)
    expect(screen.getByText('JOB #48')).toBeTruthy()
  })

  it('adopts a valid active job from a 409 response', async () => {
    startFloorPlanProcessing.mockRejectedValueOnce(
      new ProcessingJobApiError(
        'A job is already active.',
        409,
        'PROCESSING_JOB_ALREADY_ACTIVE',
        91,
      ),
    )
    renderPanel()

    fireEvent.click(screen.getByRole('button', { name: 'Start processing' }))
    await settle()

    expect(screen.getByText('JOB #91')).toBeTruthy()
    expect(screen.getByText(/Resumed monitoring the active processing job/)).toBeTruthy()
  })

  it('requires manual retry when a 409 has no valid job ID', async () => {
    startFloorPlanProcessing.mockRejectedValueOnce(
      new ProcessingJobApiError('raw conflict details', 409, 'PROCESSING_JOB_ALREADY_ACTIVE'),
    )
    renderPanel()

    fireEvent.click(screen.getByRole('button', { name: 'Start processing' }))
    await settle()

    expect(screen.getByText(/active processing job could not be resumed/)).toBeTruthy()
    expect(screen.queryByText(/raw conflict details/)).toBeNull()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy()
  })

  it('redirects a status 401 and stops polling', async () => {
    vi.useFakeTimers()
    fetchProcessingJob.mockRejectedValueOnce(
      new ProcessingJobApiError('raw auth detail', 401, 'AUTHENTICATION_REQUIRED'),
    )
    renderPanel()
    await startJob()
    await runNextPoll()
    await act(async () => vi.advanceTimersByTimeAsync(PROCESSING_POLL_INTERVAL_MS * 2))

    expect(window.location.hash).toBe('#/signin?reason=session-expired')
    expect(fetchProcessingJob).toHaveBeenCalledTimes(1)
  })

  it.each([
    [403, 'You are not authorized to monitor this processing job.'],
    [404, 'This processing job is no longer available.'],
    [422, 'The processing job address is invalid.'],
  ])('stops safely after status %s', async (status, expectedMessage) => {
    vi.useFakeTimers()
    fetchProcessingJob.mockRejectedValueOnce(
      new ProcessingJobApiError('raw private detail', status, 'SAFE_CODE'),
    )
    renderPanel()
    await startJob()
    await runNextPoll()
    await act(async () => vi.advanceTimersByTimeAsync(PROCESSING_POLL_INTERVAL_MS * 2))

    expect(screen.getByText(expectedMessage)).toBeTruthy()
    expect(screen.queryByText('raw private detail')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Retry status' })).toBeNull()
    expect(fetchProcessingJob).toHaveBeenCalledTimes(1)
  })

  it('preserves the job and offers a manual retry after a network failure', async () => {
    vi.useFakeTimers()
    fetchProcessingJob.mockRejectedValueOnce(
      new ProcessingJobApiError('raw network detail'),
    )
    renderPanel()
    await startJob()
    await runNextPoll()

    expect(screen.getByText('JOB #31')).toBeTruthy()
    expect(screen.getByText('Processing status is temporarily unavailable.')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Retry status' })).toBeTruthy()
    expect(screen.queryByText('raw network detail')).toBeNull()
  })

  it('does not automatically retry a temporary status failure', async () => {
    vi.useFakeTimers()
    fetchProcessingJob.mockRejectedValueOnce(
      new ProcessingJobApiError('temporary', 503, 'SERVICE_UNAVAILABLE'),
    )
    renderPanel()
    await startJob()
    await runNextPoll()
    await act(async () => vi.advanceTimersByTimeAsync(PROCESSING_POLL_INTERVAL_MS * 10))

    expect(fetchProcessingJob).toHaveBeenCalledTimes(1)
  })

  it('retries status without creating a new processing job', async () => {
    vi.useFakeTimers()
    fetchProcessingJob
      .mockRejectedValueOnce(new ProcessingJobApiError('temporary', 503))
      .mockResolvedValueOnce(job('processing', 44))
    renderPanel()
    await startJob()
    await runNextPoll()

    fireEvent.click(screen.getByRole('button', { name: 'Retry status' }))
    await settle()

    expect(fetchProcessingJob).toHaveBeenCalledTimes(2)
    expect(startFloorPlanProcessing).toHaveBeenCalledTimes(1)
    expect(screen.getAllByText('44%')).toHaveLength(2)
  })

  it('resumes sequential polling after a successful manual status retry', async () => {
    vi.useFakeTimers()
    fetchProcessingJob
      .mockRejectedValueOnce(new ProcessingJobApiError('temporary', 503))
      .mockResolvedValueOnce(job('processing', 44))
      .mockResolvedValueOnce(job('processing', 58))
    renderPanel()
    await startJob()
    await runNextPoll()
    fireEvent.click(screen.getByRole('button', { name: 'Retry status' }))
    await settle()

    await runNextPoll()

    expect(fetchProcessingJob).toHaveBeenCalledTimes(3)
    expect(screen.getAllByText('58%')).toHaveLength(2)
  })

  it('redirects a start 401 without showing raw details', async () => {
    startFloorPlanProcessing.mockRejectedValueOnce(
      new ProcessingJobApiError('raw OAuth detail', 401, 'AUTHENTICATION_REQUIRED'),
    )
    renderPanel()

    fireEvent.click(screen.getByRole('button', { name: 'Start processing' }))
    await settle()

    expect(window.location.hash).toBe('#/signin?reason=session-expired')
    expect(screen.queryByText('raw OAuth detail')).toBeNull()
  })

  it.each([
    [403, 'You are not authorized to start floor-plan processing.'],
    [404, 'This floor plan is no longer available.'],
    [422, 'This floor plan cannot be processed.'],
    [503, 'Floor-plan processing is temporarily unavailable.'],
  ])('shows a safe start message for status %s', async (status, expectedMessage) => {
    startFloorPlanProcessing.mockRejectedValueOnce(
      new ProcessingJobApiError('private server detail', status, 'SAFE_CODE'),
    )
    renderPanel()

    fireEvent.click(screen.getByRole('button', { name: 'Start processing' }))
    await settle()

    expect(screen.getByText(expectedMessage)).toBeTruthy()
    expect(screen.queryByText('private server detail')).toBeNull()
  })

  it('aborts a pending start request when unmounted', () => {
    let requestSignal
    startFloorPlanProcessing.mockImplementation((_, { signal }) => {
      requestSignal = signal
      return new Promise(() => {})
    })
    const view = renderPanel()
    fireEvent.click(screen.getByRole('button', { name: 'Start processing' }))

    view.unmount()

    expect(requestSignal.aborted).toBe(true)
  })

  it('aborts a pending status request when unmounted', async () => {
    vi.useFakeTimers()
    let requestSignal
    fetchProcessingJob.mockImplementation((_, { signal }) => {
      requestSignal = signal
      return new Promise(() => {})
    })
    const view = renderPanel()
    await startJob()
    await runNextPoll()

    view.unmount()

    expect(requestSignal.aborted).toBe(true)
  })

  it('clears a queued polling timer when unmounted', async () => {
    vi.useFakeTimers()
    const view = renderPanel()
    await startJob()

    view.unmount()
    await act(async () => vi.advanceTimersByTimeAsync(PROCESSING_POLL_INTERVAL_MS * 2))

    expect(fetchProcessingJob).not.toHaveBeenCalled()
  })
})
