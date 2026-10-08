import { useEffect, useRef, useState } from 'react'
import { fetchProcessingJob, startDrawingRegionProcessing } from '../../api/processingJobs.js'
import { getDemoInterpretationHref } from '../../routes/projectRoutes.js'
import { Button } from '../../components/ui/button.jsx'

export function DrawingRegionPanel({ record, region, onRegionChange, onSelectRegion, onFreezeRegion, projectId, projectFloorId, floorPlanId }) {
  const [acknowledged, setAcknowledged] = useState(false)
  const [state, setState] = useState({ status: 'idle', job: null, message: null, locked: false })
  const [refresh, setRefresh] = useState(0)
  const requestRef = useRef(null)
  const controllerRef = useRef(null)
  const inFlightRef = useRef(false)
  const jobId = state.job?.job_id
  const jobStatus = state.job?.status
  const source = record.candidate.provenance
  const plane = record.candidate.payload.source_plane
  const busy = state.status === 'submitting'
  const locked = state.locked
  const validRegion = region && [region.x, region.y].every((value) => Number.isInteger(value) && value >= 0)
    && [region.width, region.height].every((value) => Number.isInteger(value) && value > 0)
    && region.x + region.width <= plane.width_pixels && region.y + region.height <= plane.height_pixels

  useEffect(() => () => controllerRef.current?.abort(), [])
  useEffect(() => {
    if (!jobId || !['queued', 'processing'].includes(jobStatus)) return undefined
    const controller = new AbortController()
    let active = true
    let timer
    let polls = 0
    async function poll() {
      try {
        const job = await fetchProcessingJob(jobId, { signal: controller.signal })
        if (job.job_id !== jobId) throw new Error('Job identity mismatch')
        if (!active) return
        setState({ status: 'accepted', job, message: null, locked: true })
        if (['queued', 'processing'].includes(job.status)) {
          if (++polls < 40) timer = setTimeout(poll, 1500)
          else setState((current) => ({ ...current, message: 'Automatic polling paused. Refresh status to continue.' }))
        }
      } catch (error) {
        if (!active || error.name === 'AbortError') return
        setState((current) => ({ ...current, message: 'Status unavailable. Refresh this same job; do not start another.' }))
      }
    }
    poll()
    return () => { active = false; controller.abort(); clearTimeout(timer) }
  }, [jobId, jobStatus, refresh])

  async function start() {
    if (inFlightRef.current || busy || state.job || !acknowledged || !validRegion) return
    inFlightRef.current = true
    if (!requestRef.current) requestRef.current = {
      intent: 'process_drawing_region', candidate_run_id: record.candidate_run_id,
      expected_source_artifact_sha256: source.source_artifact_sha256,
      region: { ...region }, request_id: crypto.randomUUID(),
    }
    const controller = new AbortController()
    controllerRef.current = controller
    onFreezeRegion?.(requestRef.current.region)
    setState({ status: 'submitting', job: null, message: null, locked: true })
    try {
      const job = await startDrawingRegionProcessing(floorPlanId, requestRef.current, { signal: controller.signal })
      if (!controller.signal.aborted) setState({ status: 'accepted', job, message: null, locked: true })
    } catch (error) {
      if (controller.signal.aborted) return
      // A network/503 outcome is ambiguous: retain exact identity and pixels.
      const ambiguous = !error.status || error.status >= 500
      if (!ambiguous) { requestRef.current = null; onFreezeRegion?.(null) }
      setState({ status: 'error', job: null, locked: ambiguous, message: ambiguous
        ? 'Request outcome unknown. Retry the identical selection; the server reuses its job.'
        : error.existingJobId ? `Job #${error.existingJobId} is already active. This selection was not started.`
          : 'Drawing selection unavailable. Check source identity, bounds, development settings and schema initialization.' })
    } finally { inFlightRef.current = false }
  }

  return <section className="demo-approval-panel" aria-label="Drawing-only development reprocessing">
    <h2>Process a drawing region</h2>
    <p>Select one drawing, excluding title blocks and unrelated views. This uses the shared detector, not a page-specific model. Outside remains unprocessed, not empty background.</p>
    <div className="demo-add-actions">
      <Button variant="outline" disabled={locked || busy} onClick={onSelectRegion}>Select two corners</Button>
      <Button variant="outline" disabled={locked || busy || !region} onClick={() => onRegionChange(null)}>Clear region</Button>
    </div>
    <fieldset className="demo-point-fields" disabled={locked || busy}>
      <legend>Rectangle in source pixels</legend>
      {['x', 'y', 'width', 'height'].map((field) => <label key={field}>{field}
        <input aria-label={`Drawing region ${field}`} type="number" step="1" min={field === 'x' || field === 'y' ? 0 : 1}
          max={field === 'x' || field === 'width' ? plane.width_pixels : plane.height_pixels}
          value={region?.[field] ?? ''} onChange={(event) => onRegionChange({ x: 0, y: 0, width: 1, height: 1,
            ...region, [field]: Number(event.target.value) })} />
      </label>)}
    </fieldset>
    <label><input type="checkbox" checked={acknowledged} disabled={busy || Boolean(state.job)}
      onChange={(event) => setAcknowledged(event.target.checked)} /> Save this draft first if needed. The new job does not carry corrections forward; earlier reviews/layouts remain stored. Opening its result leaves unsaved edits.</label>
    <Button disabled={busy || Boolean(state.job) || !validRegion || !acknowledged} onClick={start}>
      {busy ? 'Starting…' : locked ? 'Retry identical request' : 'Process selected drawing'}
    </Button>
    {state.job && <p role="status">Job #{jobId}: {jobStatus}. {state.job.error_message || ''}</p>}
    {state.message && <p role={state.status === 'error' ? 'alert' : 'status'}>{state.message}</p>}
    {state.job && ['queued', 'processing'].includes(jobStatus) && <Button variant="outline" onClick={() => setRefresh((value) => value + 1)}>Refresh status</Button>}
    {jobStatus === 'completed' && <a href={getDemoInterpretationHref(projectId, projectFloorId, floorPlanId, jobId)}>Open new proposals for correction</a>}
    {['failed', 'cancelled'].includes(jobStatus) && <Button variant="outline" onClick={() => {
      requestRef.current = null
      onFreezeRegion?.(null)
      setState({ status: 'idle', job: null, locked: false, message: 'Previous attempt remains in history. A new request can now be started.' })
    }}>Prepare a new attempt</Button>}
  </section>
}
