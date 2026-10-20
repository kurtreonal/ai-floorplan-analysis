import { useEffect, useRef, useState } from 'react'
import { floorPlanLifecycle } from '../../api/floorPlanLifecycle.js'

export function FloorPlanLifecycleControls({ projectId, planId, restore = false, onChanged }) {
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [uncertain, setUncertain] = useState(false)
  const request = useRef(null)
  const dialog = useRef(null)
  const opener = useRef(null)
  const opening = useRef(false)
  async function open() {
    if (opening.current) return
    opening.current = true
    setBusy(true)
    setError(null)
    try {
      const value = await floorPlanLifecycle(projectId, `floor-plans/${planId}/lifecycle`)
      setPreview(value)
      request.current = { expected_revision: value.revision, request_id: crypto.randomUUID() }
    } catch (e) { setError(e.message) }
    finally { opening.current = false; setBusy(false) }
  }
  useEffect(() => {
    if (preview) dialog.current?.showModal()
  }, [preview])
  function close() {
    if (busy) return
    dialog.current?.close()
    setPreview(null)
    setError(null)
    setUncertain(false)
    request.current = null
    opener.current?.focus()
  }
  async function apply() {
    setBusy(true)
    setError(null)
    try {
      await floorPlanLifecycle(projectId, `floor-plans/${planId}${restore ? '/restore' : ''}`, {
        method: restore ? 'POST' : 'DELETE', body: request.current,
      })
      dialog.current?.close()
      setPreview(null)
      setUncertain(false)
      onChanged(planId)
    } catch (e) {
      setError(e.message)
      setUncertain(e.status === 0 || e.status >= 500)
    } finally { setBusy(false) }
  }
  const title = restore ? 'Restore floor plan' : 'Move floor plan to trash'
  return <>
    <button ref={opener} type="button" className="btn btn-outline-dark" disabled={busy} onClick={open}>
      {busy && !preview ? 'Loading…' : restore ? 'Restore' : 'Move to trash'}
    </button>
    {!preview && error && <p role="alert">{error}</p>}
    {preview && <dialog ref={dialog} className="plan-lifecycle-dialog" aria-labelledby={`plan-life-${planId}`}
      onCancel={event => { event.preventDefault(); close() }}>
      <h3 id={`plan-life-${planId}`}>{title}</h3>
      <p><strong>{preview.original_filename}</strong></p>
      <p>Plan #{preview.id} · Floor #{preview.project_floor_id}</p>
      {restore ? <p>Return this plan to the project. Cancelled analysis will not restart.</p> : <>
        <p>{preview.active_jobs ? `${preview.active_jobs} unfinished analysis job(s) will be cancelled.` : 'No unfinished analysis jobs.'}</p>
        <p>{preview.saved_layouts} saved layout(s) and {preview.saved_reviews} review(s) will be retained, along with original files and historical estimates. This plan will be excluded from current layouts, routing and quantities until restored.</p>
        <p>The floor and its other uploads are unchanged. You can restore this plan from Trash.</p>
      </>}
      {error && <p role="alert">{error}</p>}
      {uncertain && <p role="status">The response was interrupted. Retry to confirm the same request, or close and check Trash.</p>}
      <div className="plan-lifecycle-actions">
        <button className="btn btn-outline-dark" type="button" disabled={busy} onClick={close}>Cancel</button>
        <button className="btn btn-primary" type="button" disabled={busy || restore !== preview.removed} onClick={apply}>
          {busy ? 'Saving…' : uncertain ? 'Retry same request' : title}
        </button>
      </div>
    </dialog>}
  </>
}

export function FloorPlanTrash({ projectId, refreshKey, onChanged, canEdit }) {
  const [open, setOpen] = useState(false)
  const [result, setResult] = useState(null)
  const key = `${projectId}:${refreshKey}`
  const current = result?.key === key ? result : null
  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    floorPlanLifecycle(projectId, 'floor-plan-trash', { signal: controller.signal })
      .then(plans => { if (!controller.signal.aborted) setResult({ key, plans }) })
      .catch(e => { if (!controller.signal.aborted) setResult({ key, error: e.message }) })
    return () => controller.abort()
  }, [open, projectId, key])
  return <details className="floor-plan-trash" onToggle={e => {
    if (e.target !== e.currentTarget) return
    if (e.currentTarget.open) setResult(null)
    setOpen(e.currentTarget.open)
  }}>
    <summary>Trash</summary>
    {!current ? open && <p role="status">Loading…</p> : current.error ? <p role="alert">{current.error}</p> : current.plans.length === 0 ? <p>Trash is empty.</p> :
      <ul>{current.plans.map(plan => <li key={plan.id}><span>{plan.original_filename} · Floor #{plan.project_floor_id}</span>
        {canEdit && <FloorPlanLifecycleControls projectId={projectId} planId={plan.id} restore onChanged={onChanged} />}
      </li>)}</ul>}
  </details>
}
