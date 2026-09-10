import { lazy, Suspense, useEffect, useMemo, useState } from 'react'

import {
  DemoInterpretationApiError,
  fetchDemoInterpretation,
  saveDemoLayout,
  saveDemoReview,
} from '../../api/demoInterpretation.js'
import { fetchCurrentLayout, LayoutApiError } from '../../api/layouts.js'
import { fetchReviewImage } from '../../api/reviewImages.js'
import { fetchSymbolLegends } from '../../api/symbolLegends.js'
import {
  getLayoutHref,
  getProjectHref,
  getViewer3dHref,
} from '../../routes/projectRoutes.js'
import { DemoInterpretationCanvas } from './DemoInterpretationCanvas.jsx'
import './detectionReview.css'

const DraftRoomPreview = lazy(() => import('./DraftRoomPreview.jsx').then((module) => ({ default: module.DraftRoomPreview })))


function decodeImage(url) {
  return new Promise((resolve, reject) => {
    const image = new window.Image()
    image.onload = () => resolve(image)
    image.onerror = reject
    image.src = url
  })
}


function initialDraft(record) {
  if (record.review) {
    return {
      walls: record.review.walls,
      rooms: record.review.rooms,
      symbols: record.review.symbols.map((symbol) => ({
        id: symbol.id,
        disposition: symbol.disposition,
        center: symbol.center,
        symbol_legend_id: symbol.symbol_legend_id,
      })),
    }
  }
  const payload = record.candidate.payload
  return {
    walls: payload.walls.items.map((item) => ({
      id: item.id, disposition: 'accepted', start: item.start, end: item.end,
    })),
    rooms: payload.rooms.items.map((item) => ({
      id: item.id, disposition: 'accepted', name: item.label, boundary: item.boundary,
    })),
    symbols: payload.symbols.items.map((item) => ({
      id: item.id, disposition: 'accepted', center: item.center, symbol_legend_id: null,
    })),
  }
}


function errorMessage(error) {
  if (error?.status === 401) return null
  if (error?.code === 'SYMBOL_MAPPING_REQUIRED') return 'Map every accepted symbol to an approved VED legend class before completing review.'
  if (error?.code === 'METRIC_INPUTS_UNRESOLVED') return 'Approve the exact page scale and floor elevation from the project page first.'
  if (error?.code === 'SCALE_REFERENCE_MISMATCH') return 'The approved scale dimensions do not match this normalized page. Review the scale again.'
  if (error?.code === 'STALE_REVIEW_REVISION') return 'A newer review revision exists. Reload before saving.'
  if (error?.code === 'STALE_LAYOUT_VERSION') return 'A newer canonical layout exists. Reload before saving.'
  return error instanceof DemoInterpretationApiError || error instanceof LayoutApiError
    ? error.message
    : 'The floor-plan review could not be completed.'
}


function nextManualId(values, prefix) {
  const numbers = values
    .filter((item) => item.id.startsWith(`${prefix}-`))
    .map((item) => Number(item.id.slice(prefix.length + 1)))
  return `${prefix}-${String(Math.max(0, ...numbers) + 1).padStart(4, '0')}`
}


function NumericPoint({ label, value, onChange }) {
  return (
    <fieldset className="demo-point-fields">
      <legend>{label}</legend>
      {['x', 'y'].map((axis) => (
        <label key={axis}>{axis.toUpperCase()}
          <input type="number" min="0" max="1000000" step="1" value={value[axis]}
            onChange={(event) => onChange({ ...value, [axis]: Number(event.target.value) })} />
        </label>
      ))}
    </fieldset>
  )
}


export function DemoInterpretationPage({ projectId, projectFloorId, floorPlanId, processingJobId }) {
  const [state, setState] = useState({ status: 'loading', record: null, image: null, legends: [], error: null })
  const [draft, setDraft] = useState(null)
  const [selected, setSelected] = useState(null)
  const [notes, setNotes] = useState('')
  const [wallThickness, setWallThickness] = useState('')
  const [wallHeight, setWallHeight] = useState('')
  const [reviewComplete, setReviewComplete] = useState(false)
  const [approveLayout, setApproveLayout] = useState(false)
  const [saveState, setSaveState] = useState({ status: 'idle', message: null })
  const [savedLayout, setSavedLayout] = useState(null)
  const [view, setView] = useState('2d')
  const [layers, setLayers] = useState({ rooms: true, walls: false, symbols: false, source: true })

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    let objectUrl = null
    Promise.all([
      fetchDemoInterpretation(floorPlanId, { signal: controller.signal }),
      fetchReviewImage(floorPlanId, processingJobId, { signal: controller.signal }),
      fetchSymbolLegends({ signal: controller.signal }),
    ]).then(async ([record, blob, legends]) => {
      if (record.processing_job_id !== processingJobId) throw new DemoInterpretationApiError()
      objectUrl = URL.createObjectURL(blob)
      const image = await decodeImage(objectUrl)
      const plane = record.candidate.payload.source_plane
      if (image.naturalWidth !== plane.width_pixels || image.naturalHeight !== plane.height_pixels) {
        throw new DemoInterpretationApiError('The review image dimensions do not match the immutable candidate source plane.')
      }
      if (!active) return
      setState({ status: 'ready', record, image, legends, error: null })
      setDraft(initialDraft(record))
      setNotes(record.review?.evidence_notes || '')
      setWallThickness(String(record.review?.wall_thickness_meters ?? ''))
      setWallHeight(String(record.review?.wall_height_meters ?? ''))
      setReviewComplete(record.review?.review_complete || false)
      setApproveLayout(record.review?.approved_for_layout || false)
    }).catch((error) => {
      if (!active || error.name === 'AbortError') return
      if (error?.status === 401) window.location.replace('#/signin?reason=session-expired')
      else setState({ status: 'error', record: null, image: null, legends: [], error: errorMessage(error) })
    })
    return () => {
      active = false
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [floorPlanId, processingJobId])

  const selectedEntity = useMemo(() => (
    selected && draft ? draft[`${selected.kind}s`].find((item) => item.id === selected.id) : null
  ), [draft, selected])
  const savedReviewMatches = Boolean(state.record?.review
    && JSON.stringify(draft) === JSON.stringify(initialDraft(state.record))
    && notes.trim() === state.record.review.evidence_notes
    && reviewComplete === state.record.review.review_complete
    && approveLayout === state.record.review.approved_for_layout
    && (approveLayout ? Number(wallThickness) : null) === state.record.review.wall_thickness_meters
    && (approveLayout ? Number(wallHeight) : null) === state.record.review.wall_height_meters)

  function updateSelected(replacement) {
    if (!selected) return
    const key = `${selected.kind}s`
    setDraft((current) => ({
      ...current,
      [key]: current[key].map((item) => item.id === selected.id ? replacement : item),
    }))
    setSaveState({ status: 'idle', message: null })
    setReviewComplete(false)
    setApproveLayout(false)
  }

  function updateRoom(room) {
    setDraft((current) => ({ ...current, rooms: current.rooms.map((item) => item.id === room.id ? room : item) }))
    setReviewComplete(false)
    setApproveLayout(false)
  }

  function addEntity(kind) {
    const plane = state.record.candidate.payload.source_plane
    const center = { x: Math.round(plane.width_pixels / 2), y: Math.round(plane.height_pixels / 2) }
    const radius = Math.min(50, plane.width_pixels / 4, plane.height_pixels / 4)
    const key = `${kind}s`
    const prefix = `manual-${kind}`
    const id = nextManualId(draft[key], prefix)
    const entity = kind === 'wall'
      ? { id, disposition: 'accepted', start: { x: center.x - radius, y: center.y }, end: { x: center.x + radius, y: center.y } }
      : kind === 'room'
        ? { id, disposition: 'accepted', name: null, boundary: [
            { x: center.x - radius, y: center.y - radius }, { x: center.x + radius, y: center.y - radius },
            { x: center.x + radius, y: center.y + radius }, { x: center.x - radius, y: center.y + radius },
          ] }
        : { id, disposition: 'accepted', center, symbol_legend_id: null }
    setDraft((current) => ({ ...current, [key]: [...current[key], entity] }))
    setSelected({ kind, id })
    setLayers((current) => ({ ...current, [`${kind}s`]: true }))
    setView('2d')
    setReviewComplete(false)
    setApproveLayout(false)
  }

  async function saveReview({ draftOnly = false } = {}) {
    if (saveState.status === 'saving') return
    setSaveState({ status: 'saving', message: 'Saving immutable review revision…' })
    try {
      const record = await saveDemoReview(floorPlanId, {
        candidate_run_id: state.record.candidate_run_id,
        expected_revision_number: state.record.review?.revision_number ?? null,
        review_complete: draftOnly ? false : reviewComplete,
        approved_for_layout: draftOnly ? false : approveLayout,
        wall_thickness_meters: !draftOnly && approveLayout ? Number(wallThickness) : null,
        wall_height_meters: !draftOnly && approveLayout ? Number(wallHeight) : null,
        evidence_notes: notes.trim() || (draftOnly ? 'Unfinished room-first demo draft. Not approved for canonical layout.' : ''),
        ...draft,
      })
      setState((current) => ({ ...current, record }))
      setDraft(initialDraft(record))
      setNotes(record.review.evidence_notes)
      setReviewComplete(record.review.review_complete)
      setApproveLayout(record.review.approved_for_layout)
      setSaveState({ status: 'success', message: `Review revision ${record.review.revision_number} saved.` })
    } catch (error) {
      if (error?.status === 401) window.location.replace('#/signin?reason=session-expired')
      else setSaveState({ status: 'error', message: errorMessage(error) })
    }
  }

  async function publishCanonicalLayout() {
    if (!state.record.review?.approved_for_layout || !savedReviewMatches || saveState.status === 'saving') return
    setSaveState({ status: 'saving', message: 'Saving the reviewed shared canonical geometry…' })
    try {
      let expectedVersion = null
      try {
        const current = await fetchCurrentLayout(projectId, projectFloorId)
        expectedVersion = current.version_number
      } catch (error) {
        if (!(error instanceof LayoutApiError) || error.status !== 404) throw error
      }
      const layout = await saveDemoLayout(projectId, projectFloorId, floorPlanId, {
        candidate_run_id: state.record.candidate_run_id,
        review_revision_number: state.record.review.revision_number,
        expected_layout_version_number: expectedVersion,
        idempotency_key: globalThis.crypto.randomUUID(),
      })
      setSavedLayout(layout)
      setSaveState({ status: 'success', message: `Canonical layout version ${layout.version_number} saved and reloaded.` })
    } catch (error) {
      if (error?.status === 401) window.location.replace('#/signin?reason=session-expired')
      else setSaveState({ status: 'error', message: errorMessage(error) })
    }
  }

  if (state.status === 'loading') return <div className="detection-state" role="status">Loading unified room, wall, and symbol proposals…</div>
  if (state.status === 'error') return <section className="detection-state detection-error"><p role="alert">{state.error}</p><a href={getProjectHref(projectId)}>Back to project</a></section>

  const plane = state.record.candidate.payload.source_plane
  const truncated = ['walls', 'rooms', 'symbols'].filter(
    (key) => state.record.candidate.payload[key].truncated,
  )
  return (
    <article className="detection-review-page demo-review-page">
      <a className="detection-back-link" href={getProjectHref(projectId)}>← Back to project</a>
      <nav className="demo-steps" aria-label="Floor-plan workflow">
        <a href={getProjectHref(projectId)}>1 · Upload &amp; analyze</a>
        <strong aria-current="step">2 · Explore rooms in 2D / 3D</strong>
        <a href="#demo-approval-title" onClick={(event) => { event.preventDefault(); document.getElementById('demo-approval-title')?.scrollIntoView({ behavior: 'smooth' }) }}>3 · Save &amp; approve when ready</a>
      </nav>
      <header className="detection-review-header">
        <div><span className="mono">LOCAL DEMO REVIEW · JOB #{processingJobId}</span><h1>Correct floor-plan proposals</h1></div>
        <p>{draft.rooms.filter((item) => item.disposition !== 'rejected').length} room proposals · unfinished demo</p>
      </header>
      <p role="note">Draft room shapes from image processing—not measured or approved. Correct mistakes in 2D before using them.</p>
      {truncated.length > 0 && <p className="detection-limit-warning" role="alert">Bounded proposal cap reached for: {truncated.join(', ')}. Add missing geometry manually where needed.</p>}
      {state.legends.length === 0 && <details><summary>Do I need a symbol legend?</summary><p>Not for this room preview. Electrical-symbol approval still needs an approved VED legend.</p></details>}

      <section className="demo-preview-workspace" aria-label="Room-first workspace">
        <div className="demo-workspace-toolbar">
          <div className="demo-view-switch" role="group" aria-label="Preview mode">
            <button type="button" aria-pressed={view === '2d'} onClick={() => setView('2d')}>2D · Review rooms</button>
            <button type="button" aria-pressed={view === '3d'} onClick={() => setView('3d')}>3D · Draft preview</button>
          </div>
          <button type="button" disabled={saveState.status === 'saving'} onClick={() => saveReview({ draftOnly: true })}>Save unfinished draft</button>
        </div>
        <p className="demo-next-step">{view === '2d' ? 'Start here: click a purple room to select it. Drag its corner handles to correct the shape, then open 3D. Nothing is approved automatically.' : 'This is an illustrative preview of your current room shapes. You can return to 2D at any time.'}</p>
        {view === '2d' ? <>
          <div className="demo-layer-controls">{Object.keys(layers).map((key) => <label key={key}><input type="checkbox" checked={layers[key]} onChange={(event) => setLayers((current) => ({ ...current, [key]: event.target.checked }))} />Show {key === 'source' ? 'original plan' : `${key} proposals`}</label>)}</div>
          {draft.rooms.length === 0 && <p role="status">No enclosed rooms were found. Add a missing room below and drag its corners over the plan.</p>}
          <DemoInterpretationCanvas image={state.image} width={plane.width_pixels} height={plane.height_pixels} draft={draft} selected={selected} onSelect={setSelected} layers={layers} onUpdateRoom={updateRoom} />
        </> : <Suspense fallback={<p role="status">Opening draft 3D preview…</p>}><DraftRoomPreview draft={draft} width={plane.width_pixels} height={plane.height_pixels} projectId={projectId} /></Suspense>}
        {saveState.message && <p role={saveState.status === 'error' ? 'alert' : 'status'}>{saveState.message}</p>}
      </section>

      <section className="demo-review-tools" aria-labelledby="demo-tools-title" hidden={view !== '2d'}>
        <h2 id="demo-tools-title">Review and correct</h2>
        <div className="demo-add-actions">
          {['wall', 'room', 'symbol'].map((kind) => <button key={kind} type="button" className="btn btn-outline-dark" onClick={() => addEntity(kind)}>Add missing {kind}</button>)}
        </div>
        <label>Select proposal
          <select value={selected ? `${selected.kind}:${selected.id}` : ''} onChange={(event) => {
            const [kind, id] = event.target.value.split(':')
            setSelected(event.target.value ? { kind, id } : null)
            if (event.target.value) setLayers((current) => ({ ...current, [`${kind}s`]: true }))
          }}>
            <option value="">Choose an item</option>
            {['room', 'wall', 'symbol'].filter((kind) => layers[`${kind}s`]).flatMap((kind) => draft[`${kind}s`].map((item) => <option key={`${kind}:${item.id}`} value={`${kind}:${item.id}`}>{kind} · {item.name || item.id} · {item.disposition === 'rejected' ? 'excluded' : 'in draft'}</option>))}
          </select>
        </label>
        {selectedEntity && <div className="demo-selected-editor">
          <h3>{selected.kind} {selectedEntity.id}</h3>
          <label>Review decision
            <select value={selectedEntity.disposition} onChange={(event) => updateSelected({ ...selectedEntity, disposition: event.target.value })}>
              <option value="accepted">Accept</option><option value="rejected">Reject</option>
            </select>
          </label>
          {selected.kind === 'wall' && <><NumericPoint label="Start point" value={selectedEntity.start} onChange={(start) => updateSelected({ ...selectedEntity, start })} /><NumericPoint label="End point" value={selectedEntity.end} onChange={(end) => updateSelected({ ...selectedEntity, end })} /></>}
          {selected.kind === 'room' && <>
            <label>Room name<input value={selectedEntity.name || ''} maxLength="255" onChange={(event) => updateSelected({ ...selectedEntity, name: event.target.value || null })} /></label>
            <div className="demo-room-points">{selectedEntity.boundary.map((point, index) => <NumericPoint key={`${selectedEntity.id}-${index}`} label={`Boundary point ${index + 1}`} value={point} onChange={(nextPoint) => updateSelected({ ...selectedEntity, boundary: selectedEntity.boundary.map((item, pointIndex) => pointIndex === index ? nextPoint : item) })} />)}</div>
          </>}
          {selected.kind === 'symbol' && <>
            <NumericPoint label="Symbol center" value={selectedEntity.center} onChange={(center) => updateSelected({ ...selectedEntity, center })} />
            <label>Approved VED legend class<select value={selectedEntity.symbol_legend_id || ''} onChange={(event) => updateSelected({ ...selectedEntity, symbol_legend_id: event.target.value ? Number(event.target.value) : null })}>
              <option value="">Unmapped</option>{state.legends.map((legend) => <option key={legend.id} value={legend.id}>{legend.class_id} — {legend.name}</option>)}
            </select></label>
          </>}
        </div>}
      </section>

      <section className="demo-approval-panel" aria-labelledby="demo-approval-title">
        <h2 id="demo-approval-title">Optional: approve a measured, saved layout</h2>
        <p>You do not need this step for the draft 2D / 3D preview above. Use it only after reviewing geometry and real dimensions. Saving an unfinished draft does not approve it.</p>
        <p>Before layout approval, use “Review scale and elevation” on the project page. Required normalized dimensions: {plane.width_pixels} × {plane.height_pixels} pixels.</p>
        <label>Review evidence notes<textarea required maxLength="1000" value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
        <label><input type="checkbox" checked={reviewComplete} onChange={(event) => { setReviewComplete(event.target.checked); if (!event.target.checked) setApproveLayout(false) }} /> I reviewed every proposed and manually added item against the visible page.</label>
        <label><input type="checkbox" checked={approveLayout} disabled={!reviewComplete} onChange={(event) => setApproveLayout(event.target.checked)} /> I approve accepted geometry and create the reviewed symbols as my placements in this planning layout.</label>
        {approveLayout && <div className="demo-wall-dimensions">
          <label>Wall thickness (meters)<input type="number" min="0.01" max="1000" step="any" value={wallThickness} onChange={(event) => setWallThickness(event.target.value)} /></label>
          <label>Wall height (meters)<input type="number" min="0.01" max="1000" step="any" value={wallHeight} onChange={(event) => setWallHeight(event.target.value)} /></label>
        </div>}
        <div className="demo-add-actions">
          <button type="button" className="btn btn-dark" disabled={!notes.trim() || saveState.status === 'saving'} onClick={saveReview}>Save review revision</button>
          <button type="button" className="btn btn-accent" disabled={!state.record.review?.approved_for_layout || !savedReviewMatches || saveState.status === 'saving'} onClick={publishCanonicalLayout}>Save shared canonical layout</button>
        </div>
        {savedLayout && <p><a href={getLayoutHref(projectId, projectFloorId)}>Open aligned 2D layout</a> · <a href={getViewer3dHref(projectId, projectFloorId)}>Open aligned 3D layout</a></p>}
      </section>
    </article>
  )
}
