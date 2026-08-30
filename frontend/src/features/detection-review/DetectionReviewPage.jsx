import { useEffect, useState } from 'react'

import { DetectionApiError, fetchDetectionResults } from '../../api/detections.js'
import {
  DetectionClassificationApiError,
  putDetectionClassification,
} from '../../api/detectionClassifications.js'
import { DetectionReviewApiError, putDetectionReview } from '../../api/detectionReviews.js'
import { fetchReviewImage, ReviewImageApiError } from '../../api/reviewImages.js'
import {
  createPlacementRequestId,
  ManualSymbolApiError,
  postManualSymbol,
} from '../../api/manualSymbols.js'
import { fetchSymbolLegends, SymbolLegendApiError } from '../../api/symbolLegends.js'
import { getProjectHref } from '../../routes/projectRoutes.js'
import { DetectionInspector } from './DetectionInspector.jsx'
import { DetectionReviewCanvas } from './DetectionReviewCanvas.jsx'
import { manualSelectionKey, STATUS_PRESENTATION } from './detectionCanvasGeometry.js'
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
  if (error instanceof SymbolLegendApiError) return 'The approved symbol classes could not be loaded safely.'
  return 'Detection review is temporarily unavailable.'
}

export function DetectionReviewPage({ projectId, floorPlanId, processingJobId }) {
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState({ status: 'loading', results: null, image: null, legends: null, error: null })
  const [selectedKey, setSelectedKey] = useState(null)
  const [reviewState, setReviewState] = useState({ status: 'idle', message: null })
  const [classificationState, setClassificationState] = useState({ status: 'idle', message: null })
  const [manualLegendId, setManualLegendId] = useState('')
  const [placement, setPlacement] = useState({ mode: false, draft: null, requestId: null, status: 'idle', message: null })

  useEffect(() => {
    const controller = new AbortController()
    let objectUrl = null
    let active = true
    async function load() {
      try {
        const [results, blob, legends] = await Promise.all([
          fetchDetectionResults(floorPlanId, processingJobId, { signal: controller.signal }),
          fetchReviewImage(floorPlanId, processingJobId, { signal: controller.signal }),
          fetchSymbolLegends({ signal: controller.signal }),
        ])
        objectUrl = URL.createObjectURL(blob)
        const image = await decodeImage(objectUrl)
        if (!active) return
        const dimensioned = [...results.symbols, ...results.manual_symbols]
        if (dimensioned.length > 0 && (
          dimensioned[0].image_width_pixels !== image.naturalWidth
          || dimensioned[0].image_height_pixels !== image.naturalHeight
        )) throw new DetectionApiError()
        setState({ status: 'ready', results, image, legends, error: null })
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
        setState({ status: 'error', results: null, image: null, legends: null, error: safeMessage(error) })
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
  const imageWidth = results?.symbols[0]?.image_width_pixels || results?.manual_symbols[0]?.image_width_pixels || state.image?.naturalWidth
  const imageHeight = results?.symbols[0]?.image_height_pixels || results?.manual_symbols[0]?.image_height_pixels || state.image?.naturalHeight
  const selectedDetectedId = selectedKey?.startsWith('detected:')
    ? Number(selectedKey.slice('detected:'.length))
    : null

  function retry() {
    setState({ status: 'loading', results: null, image: null, legends: null, error: null })
    setSelectedKey(null)
    setReviewState({ status: 'idle', message: null })
    setClassificationState({ status: 'idle', message: null })
    setManualLegendId('')
    setPlacement({ mode: false, draft: null, requestId: null, status: 'idle', message: null })
    setAttempt((value) => value + 1)
  }

  async function submitReview(decision) {
    if (reviewState.status === 'saving' || !selectedDetectedId) return
    setReviewState({ status: 'saving', message: 'Saving Designer decision...' })
    try {
      const review = await putDetectionReview(
        floorPlanId,
        processingJobId,
        selectedDetectedId,
        decision,
      )
      setState((current) => ({
        ...current,
        results: {
          ...current.results,
          symbols: current.results.symbols.map((symbol) => (
            symbol.id === selectedDetectedId
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

  async function submitClassification(symbolLegendId) {
    if (classificationState.status === 'saving' || !selectedDetectedId) return
    setClassificationState({ status: 'saving', message: 'Saving corrected classification...' })
    try {
      const response = await putDetectionClassification(
        floorPlanId,
        processingJobId,
        selectedDetectedId,
        symbolLegendId,
      )
      setState((current) => ({
        ...current,
        results: {
          ...current.results,
          symbols: current.results.symbols.map((symbol) => (
            symbol.id === selectedDetectedId
              ? {
                  ...symbol,
                  authoritative_class: {
                    id: response.authoritative_class.id,
                    name: response.authoritative_class.name,
                  },
                  correction: response.sequence_number === null ? null : {
                    sequence_number: response.sequence_number,
                    old_class: { id: response.old_class.id, name: response.old_class.name },
                    new_class: { id: response.new_class.id, name: response.new_class.name },
                    corrected_at: response.corrected_at,
                  },
                }
              : symbol
          )),
        },
      }))
      setClassificationState({
        status: 'success',
        message: response.sequence_number === null
          ? 'The original AI classification is authoritative again.'
          : `Classification corrected to ${response.authoritative_class.name}.`,
      })
    } catch (error) {
      if (error?.status === 401) {
        window.location.replace('#/signin?reason=session-expired')
        return
      }
      const message = error instanceof DetectionClassificationApiError && error.status === 403
        ? 'You are not authorized to correct this detection.'
        : error instanceof DetectionClassificationApiError && error.status === 404
          ? 'The selected detection is no longer available.'
          : error instanceof DetectionClassificationApiError && error.status === 409
            ? 'That approved symbol class is no longer available. Reload and choose another class.'
            : error instanceof DetectionClassificationApiError && error.status === 422
              ? 'The classification request was invalid. Choose an approved class and try again.'
              : 'The classification correction could not be saved. Please try again.'
      setClassificationState({ status: 'error', message })
    }
  }

  function beginPlacement() {
    if (!Number.isSafeInteger(Number(manualLegendId)) || Number(manualLegendId) <= 0) return
    try {
      setPlacement({
        mode: true,
        draft: null,
        requestId: createPlacementRequestId(),
        status: 'idle',
        message: 'Placement mode active. Click or tap the normalized plan.',
      })
    } catch {
      setPlacement({ mode: false, draft: null, requestId: null, status: 'error', message: 'Manual placement could not be started safely.' })
    }
  }

  function cancelPlacement() {
    setPlacement({ mode: false, draft: null, requestId: null, status: 'idle', message: 'Manual placement cancelled.' })
  }

  function placeDraft(center) {
    setPlacement((current) => ({
      ...current,
      draft: center,
      status: 'idle',
      message: `Draft position: ${center.x}, ${center.y} source pixels.`,
    }))
  }

  async function saveManualSymbol() {
    if (placement.status === 'saving' || !placement.draft || !placement.requestId) return
    setPlacement((current) => ({ ...current, status: 'saving', message: 'Saving manual symbol...' }))
    try {
      const symbol = await postManualSymbol(
        floorPlanId,
        processingJobId,
        placement.requestId,
        Number(manualLegendId),
        placement.draft,
      )
      setState((current) => ({
        ...current,
        results: {
          ...current.results,
          manual_symbols: [
            ...current.results.manual_symbols.filter((item) => item.id !== symbol.id),
            symbol,
          ].sort((left, right) => left.id - right.id),
        },
      }))
      setSelectedKey(manualSelectionKey(symbol.id))
      setPlacement({ mode: false, draft: null, requestId: null, status: 'success', message: 'Manual symbol saved successfully.' })
    } catch (error) {
      if (error?.status === 401) {
        window.location.replace('#/signin?reason=session-expired')
        return
      }
      const message = error instanceof ManualSymbolApiError && error.status === 403
        ? 'You are not authorized to add a manual symbol.'
        : error instanceof ManualSymbolApiError && error.status === 404
          ? 'The selected review context is no longer available.'
          : error instanceof ManualSymbolApiError && error.status === 409
            ? 'The approved class or aligned review image is no longer available. Reload before placing another symbol.'
            : error instanceof ManualSymbolApiError && error.status === 422
              ? 'The draft position is invalid. Place it within the normalized plan.'
              : 'The manual symbol could not be saved. Please retry this draft.'
      setPlacement((current) => ({ ...current, status: 'error', message }))
    }
  }

  return (
    <div className="detection-review-page">
      <a className="detection-back-link" href={getProjectHref(projectId)}>← Back to project</a>
      <header className="detection-review-header">
        <div><span className="mono">DETECTION REVIEW · JOB #{processingJobId}</span><h1>Review AI detection results</h1></div>
        {results && <p>{results.walls.length} walls · {results.symbols.length} AI symbols · {results.manual_symbols.length} manual symbols</p>}
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
          <section className="manual-placement-controls" aria-labelledby="manual-placement-title">
            <h2 id="manual-placement-title">Add a missing symbol</h2>
            {state.legends.length === 0 ? (
              <p>No approved symbol classes are configured. Manual placement is unavailable.</p>
            ) : (
              <>
                <label htmlFor="manual-symbol-legend">Approved class for manual symbol</label>
                <select id="manual-symbol-legend" value={manualLegendId} disabled={placement.status === 'saving'} onChange={(event) => setManualLegendId(event.target.value)}>
                  <option value="">Choose an approved class</option>
                  {state.legends.map((legend) => <option key={legend.id} value={legend.id}>{legend.class_id} — {legend.name}</option>)}
                </select>
                {!placement.mode ? (
                  <button className="btn btn-dark" type="button" disabled={!manualLegendId} onClick={beginPlacement}>Add missing symbol</button>
                ) : (
                  <div className="manual-placement-actions">
                    <p>Click or tap the normalized plan to set or move the draft marker.</p>
                    <p>Draft coordinates: {placement.draft ? `${placement.draft.x}, ${placement.draft.y}` : 'Not placed'}</p>
                    <button className="btn btn-dark" type="button" disabled={!placement.draft || placement.status === 'saving'} onClick={saveManualSymbol}>Save symbol</button>
                    <button className="btn" type="button" disabled={placement.status === 'saving'} onClick={cancelPlacement}>Cancel placement</button>
                  </div>
                )}
              </>
            )}
            <div className={`detection-review-announcement is-${placement.status}`} role={placement.status === 'error' ? 'alert' : 'status'} aria-live="polite">{placement.message}</div>
          </section>
          <DetectionReviewCanvas image={state.image} imageWidth={imageWidth} imageHeight={imageHeight} walls={results.walls} symbols={results.symbols} manualSymbols={results.manual_symbols} selectedKey={selectedKey} onSelect={setSelectedKey} placementMode={placement.mode} draft={placement.draft} onPlace={placeDraft} />
          <div className={`detection-review-announcement is-${reviewState.status}`} role={reviewState.status === 'error' ? 'alert' : 'status'} aria-live="polite">{reviewState.message}</div>
          <div className={`detection-review-announcement is-${classificationState.status}`} role={classificationState.status === 'error' ? 'alert' : 'status'} aria-live="polite">{classificationState.message}</div>
          <DetectionInspector symbols={results.symbols} manualSymbols={results.manual_symbols} legends={state.legends} selectedKey={selectedKey} onSelect={setSelectedKey} onReview={submitReview} reviewStatus={reviewState.status} onClassification={submitClassification} classificationStatus={classificationState.status} />
        </>
      )}
    </div>
  )
}
