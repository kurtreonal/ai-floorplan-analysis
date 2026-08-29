import { useEffect, useRef, useState } from 'react'

import {
  fetchProcessingJob,
  ProcessingJobApiError,
  startFloorPlanProcessing,
} from '../../api/processingJobs.js'
import { getDetectionReviewHref } from '../../routes/projectRoutes.js'


export const PROCESSING_POLL_INTERVAL_MS = 2000

const ACTIVE_STATUSES = new Set(['queued', 'processing'])

function redirectToSignIn() {
  window.location.replace('#/signin?reason=session-expired')
}

function statusFailureMessage(error) {
  if (error instanceof ProcessingJobApiError) {
    if (error.status === 403) return 'You are not authorized to monitor this processing job.'
    if (error.status === 404) return 'This processing job is no longer available.'
    if (error.status === 422) return 'The processing job address is invalid.'
  }
  return 'Processing status is temporarily unavailable.'
}

function startFailureMessage(error) {
  if (error instanceof ProcessingJobApiError) {
    if (error.status === 403) return 'You are not authorized to start floor-plan processing.'
    if (error.status === 404) return 'This floor plan is no longer available.'
    if (error.status === 422) return 'This floor plan cannot be processed.'
    if (error.status === 409) return 'An active processing job could not be resumed. Try again manually.'
  }
  return 'Floor-plan processing is temporarily unavailable.'
}

export function ProcessingJobPanel({ projectId, floorPlanId, originalFilename }) {
  const [viewState, setViewState] = useState('ready')
  const [job, setJob] = useState(null)
  const [message, setMessage] = useState(null)
  const mountedRef = useRef(true)
  const timerRef = useRef(null)
  const startControllerRef = useRef(null)
  const statusControllerRef = useRef(null)
  const startLockedRef = useRef(false)
  const statusInFlightRef = useRef(false)
  const generationRef = useRef(0)

  function clearTimer() {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }

  function cancelStatusRequest() {
    clearTimer()
    statusControllerRef.current?.abort()
    statusControllerRef.current = null
    statusInFlightRef.current = false
  }

  function schedulePoll(jobId, generation, delay = PROCESSING_POLL_INTERVAL_MS) {
    clearTimer()
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null
      pollJob(jobId, generation)
    }, delay)
  }

  async function pollJob(jobId, generation) {
    if (
      !mountedRef.current
      || generation !== generationRef.current
      || statusInFlightRef.current
    ) {
      return
    }

    const controller = new AbortController()
    statusControllerRef.current = controller
    statusInFlightRef.current = true

    try {
      const nextJob = await fetchProcessingJob(jobId, { signal: controller.signal })
      if (!mountedRef.current || generation !== generationRef.current) return

      setJob(nextJob)
      setViewState(nextJob.status)
      setMessage(null)
      if (ACTIVE_STATUSES.has(nextJob.status)) {
        schedulePoll(jobId, generation)
      }
    } catch (error) {
      if (
        error.name === 'AbortError'
        || !mountedRef.current
        || generation !== generationRef.current
      ) {
        return
      }
      clearTimer()
      if (error instanceof ProcessingJobApiError && error.status === 401) {
        generationRef.current += 1
        redirectToSignIn()
        return
      }
      setMessage(statusFailureMessage(error))
      setViewState(
        error instanceof ProcessingJobApiError
        && [403, 404, 422].includes(error.status)
          ? 'unavailable'
          : 'monitor_error',
      )
    } finally {
      if (statusControllerRef.current === controller) {
        statusControllerRef.current = null
        statusInFlightRef.current = false
      }
    }
  }

  function adoptJob(jobId, notice = null) {
    cancelStatusRequest()
    generationRef.current += 1
    const generation = generationRef.current
    setJob({
      job_id: jobId,
      type: 'floor_plan_analysis',
      status: 'queued',
      progress: 0,
      error_message: null,
    })
    setViewState('queued')
    setMessage(notice)
    schedulePoll(jobId, generation)
  }

  async function startProcessing() {
    if (startLockedRef.current) return

    startLockedRef.current = true
    startControllerRef.current?.abort()
    cancelStatusRequest()
    generationRef.current += 1
    setViewState('starting')
    setMessage(null)

    const controller = new AbortController()
    startControllerRef.current = controller
    try {
      const startedJob = await startFloorPlanProcessing(floorPlanId, {
        signal: controller.signal,
      })
      if (mountedRef.current && startControllerRef.current === controller) {
        adoptJob(startedJob.job_id)
      }
    } catch (error) {
      if (error.name === 'AbortError' || !mountedRef.current) return
      if (error instanceof ProcessingJobApiError && error.status === 401) {
        redirectToSignIn()
        return
      }
      if (
        error instanceof ProcessingJobApiError
        && error.status === 409
        && error.existingJobId !== null
      ) {
        adoptJob(error.existingJobId, 'Resumed monitoring the active processing job.')
        return
      }
      setJob(null)
      setMessage(startFailureMessage(error))
      setViewState('start_error')
    } finally {
      if (startControllerRef.current === controller) {
        startControllerRef.current = null
        startLockedRef.current = false
      }
    }
  }

  function retryStatus() {
    if (!job || statusInFlightRef.current) return
    setMessage(null)
    setViewState(job.status)
    pollJob(job.job_id, generationRef.current)
  }

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      generationRef.current += 1
      clearTimer()
      startControllerRef.current?.abort()
      statusControllerRef.current?.abort()
    }
  }, [])

  const progress = job?.progress ?? 0
  const isActive = viewState === 'queued' || viewState === 'processing'

  return (
    <section
      className={`processing-job-panel processing-job-${viewState}`}
      aria-label={`Processing controls for ${originalFilename}`}
    >
      <div className="processing-job-heading">
        <div>
          <span className="mono">AI PROCESSING</span>
          <h4>Floor-plan analysis</h4>
        </div>
        {job && <span className="processing-job-id mono">JOB #{job.job_id}</span>}
      </div>

      {viewState === 'ready' && (
        <>
          <p>Ready to create a processing job for this uploaded floor plan.</p>
          <button className="btn btn-dark" type="button" onClick={startProcessing}>
            Start processing
          </button>
        </>
      )}

      {viewState === 'starting' && (
        <div className="processing-job-live" role="status" aria-live="polite">
          <span className="auth-spinner" aria-hidden="true" />
          <span>Starting processing…</span>
          <button className="btn btn-dark" type="button" disabled>
            Starting…
          </button>
        </div>
      )}

      {isActive && (
        <div className="processing-job-active" role="status" aria-live="polite">
          {message && <p className="processing-job-notice">{message}</p>}
          <div className="processing-job-statusline">
            <strong>{viewState === 'queued' ? 'Queued' : 'Processing'}</strong>
            <span>{progress}%</span>
          </div>
          <progress value={progress} max="100" aria-label="Processing progress">
            {progress}%
          </progress>
          <p>Monitoring job #{job.job_id}. Progress is reported by the backend.</p>
        </div>
      )}

      {viewState === 'completed' && (
        <div className="processing-job-result processing-job-success" role="status">
          <strong>Processing completed.</strong>
          <p>Persisted AI results are ready for read-only review.</p>
          <a className="btn btn-outline-dark" href={getDetectionReviewHref(projectId, floorPlanId, job.job_id)}>
            Review detections
          </a>
        </div>
      )}

      {viewState === 'failed' && (
        <div className="processing-job-result processing-job-failure" role="alert">
          <strong>Processing failed.</strong>
          <p>{job.error_message || 'The processing job failed without a public error message.'}</p>
          <button className="btn btn-outline-dark" type="button" onClick={startProcessing}>
            Retry processing
          </button>
        </div>
      )}

      {viewState === 'cancelled' && (
        <div className="processing-job-result" role="status">
          <strong>Processing was cancelled.</strong>
          <p>You can start a new processing attempt.</p>
          <button className="btn btn-outline-dark" type="button" onClick={startProcessing}>
            Start new attempt
          </button>
        </div>
      )}

      {viewState === 'monitor_error' && (
        <div className="processing-job-result processing-job-failure" role="alert">
          <strong>Monitoring paused.</strong>
          <p>{message}</p>
          <button className="btn btn-outline-dark" type="button" onClick={retryStatus}>
            Retry status
          </button>
        </div>
      )}

      {viewState === 'unavailable' && (
        <div className="processing-job-result processing-job-failure" role="alert">
          <strong>Monitoring stopped.</strong>
          <p>{message}</p>
        </div>
      )}

      {viewState === 'start_error' && (
        <div className="processing-job-result processing-job-failure" role="alert">
          <strong>Processing did not start.</strong>
          <p>{message}</p>
          <button className="btn btn-outline-dark" type="button" onClick={startProcessing}>
            Try again
          </button>
        </div>
      )}
    </section>
  )
}
