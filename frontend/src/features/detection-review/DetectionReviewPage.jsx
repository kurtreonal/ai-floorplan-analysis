import { useEffect, useState } from 'react'

import { DetectionApiError, fetchDetectionResults } from '../../api/detections.js'
import { DetectionReviewApiError, putDetectionReview } from '../../api/detectionReviews.js'
import { fetchReviewImage, ReviewImageApiError } from '../../api/reviewImages.js'
import { getProjectHref } from '../../routes/projectRoutes.js'
import { DetectionInspector } from './DetectionInspector.jsx'
import { DetectionReviewCanvas } from './DetectionReviewCanvas.jsx'
import { STATUS_PRESENTATION } from './detectionCanvasGeometry.js'
import './detectionReview.css'

function decodeImage(url) {
  return new Promise((resolve, reject) => {
    const image = new window.Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('decode failed'))
    image.src = url
  })
}

function safeMessage(error) {
  if (error?.status === 404) return 'The requested review data or aligned blueprint reference is unavailable.'
  if (error?.status === 403) return 'The requested review data is unavailable.'
  if (error?.status === 422) return 'The detection review address is invalid.'
  if (error instanceof DetectionApiError) return 'Detection results could not be loaded safely.'
  if (error instanceof ReviewImageApiError) return 'The aligned blueprint reference is temporarily unavailable.'
  return 'Detection review is temporarily unavailable.'
}

export function DetectionReviewPage({ projectId, floorPlanId, processingJobId }) {
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState({ status: 'loading', results: null, image: null, error: null })
  const [selectedId, setSelectedId] = useState(null)
  const [reviewState, setReviewState] = useState({ status: 'idle', message: null })

  useEffect(() => {
    const controller = new AbortController()
    let objectUrl = null
    let active = true
    async function load() {
      try {
        const [results, blob] = await Promise.all([
          fetchDetectionResults(floorPlanId, processingJobId, { signal: controller.signal }),
          fetchReviewImage(floorPlanId, processingJobId, { signal: controller.signal }),
        ])
        objectUrl = URL.createObjectURL(blob)
        const image = await decodeImage(objectUrl)
        if (!active) return
        if (results.symbols.length > 0 && (
          results.symbols[0].image_width_pixels !== image.naturalWidth
          || results.symbols[0].image_height_pixels !== image.naturalHeight
        )) throw new DetectionApiError()
        setState({ status: 'ready', results, image, error: null })
      } catch (error) {
        if (!active || error.name === 'AbortError') return
        if (error?.status === 401) {
          window.location.replace('#/signin?reason=session-expired')
          return
        }
        if (objectUrl) {
          URL.revokeObjectURL(objectUrl)
          objectUrl = null
        }
        setState({ status: 'error', results: null, image: null, error: safeMessage(error) })
      }
    }
    load()
    return () => {
      active = false
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [attempt, floorPlanId, processingJobId])

  const results = state.results
  const imageWidth = results?.symbols[0]?.image_width_pixels || state.image?.naturalWidth
  const imageHeight = results?.symbols[0]?.image_height_pixels || state.image?.naturalHeight

  function retry() {
    setState({ status: 'loading', results: null, image: null, error: null })
    setSelectedId(null)
    setAttempt((value) => value + 1)
  }

  async function submitReview(decision) {
    if (reviewState.status === 'saving' || !selectedId) return
    setReviewState({ status: 'saving', message: 'Saving Designer decision...' })
    try {
      const review = await putDetectionReview(
        floorPlanId,
        processingJobId,
        selectedId,
        decision,
      )
      setState((current) => ({
        ...current,
        results: {
          ...current.results,
          symbols: current.results.symbols.map((symbol) => (
            symbol.id === selectedId
              ? {
                  ...symbol,
                  review: {
                    decision: review.decision,
                    sequence_number: review.sequence_number,
                    reviewed_at: review.reviewed_at,
                  },
                }
              : symbol
          )),
        },
      }))
      setReviewState({
        status: 'success',
        message: review.decision === 'confirmed'
          ? 'Detection confirmed successfully.'
          : 'Detection rejected successfully. The original AI result remains visible.',
      })
    } catch (error) {
      if (error?.status === 401) {
        window.location.replace('#/signin?reason=session-expired')
        return
      }
      const message = error instanceof DetectionReviewApiError && error.status === 403
        ? 'You are not authorized to review this detection.'
        : error instanceof DetectionReviewApiError && error.status === 404
          ? 'The selected detection is no longer available for review.'
          : error instanceof DetectionReviewApiError && error.status === 422
            ? 'The review request was invalid. Select the detection and try again.'
            : 'The Designer decision could not be saved. Please try again.'
      setReviewState({ status: 'error', message })
    }
  }

  return (
    <div className="detection-review-page">
      <a className="detection-back-link" href={getProjectHref(projectId)}>← Back to project</a>
      <header className="detection-review-header">
        <div><span className="mono">DETECTION REVIEW · JOB #{processingJobId}</span><h1>Review AI detection results</h1></div>
        {results && <p>{results.walls.length} walls · {results.symbols.length} symbols</p>}
      </header>
      {state.status === 'loading' && <div className="detection-state" role="status">Loading the normalized blueprint and detection results…</div>}
      {state.status === 'error' && (
        <div className="detection-state detection-error" role="alert">
          <p>{state.error}</p><button className="btn btn-dark" type="button" onClick={retry}>Retry</button>
        </div>
      )}
      {state.status === 'ready' && (
        <>
          {results.symbols.some((symbol) => symbol.detection_limit_reached) && (
            <div className="detection-limit-warning" role="alert">The model reached its configured result cap. Displayed results may be incomplete.</div>
          )}
          <div className="detection-legend" aria-label="Detection status legend">
            {['detected', 'needs_review', 'verified'].map((status) => <span key={status}><i className={`legend-${status}`} />{STATUS_PRESENTATION[status].label}</span>)}
          </div>
          <DetectionReviewCanvas image={state.image} imageWidth={imageWidth} imageHeight={imageHeight} walls={results.walls} symbols={results.symbols} selectedId={selectedId} onSelect={setSelectedId} />
          <div className={`detection-review-announcement is-${reviewState.status}`} role={reviewState.status === 'error' ? 'alert' : 'status'} aria-live="polite">{reviewState.message}</div>
          <DetectionInspector symbols={results.symbols} selectedId={selectedId} onSelect={setSelectedId} onReview={submitReview} reviewStatus={reviewState.status} />
        </>
      )}
    </div>
  )
}
