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
      id: item.id,
      disposition: 'accepted',
      start: item.start,
      end: item.end,
      estimated_thickness_pixels: item.estimated_thickness_pixels ?? 12,
    })),
    rooms: payload.rooms.items.map((item) => ({
      id: item.id,
      disposition: 'accepted',
      name: item.label,
      boundary: item.boundary,
    })),
    symbols: payload.symbols.items.map((item) => ({
      id: item.id,
      disposition: 'accepted',
      center: item.center,
      symbol_legend_id: null,
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
  // Default to wall-focused view with rooms hidden
  const [layers, setLayers] = useState({ walls: true, rooms: false, symbols: false, source: true })
  const [tool, setTool] = useState('move') // 'move' | 'draw' | 'delete'
  const [blueprintOpacity, setBlueprintOpacity] = useState(1.0)
  const [history, setHistory] = useState([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [staleRoomsWarning, setStaleRoomsWarning] = useState(false)

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
      const initial = initialDraft(record)
      setState({ status: 'ready', record, image, legends, error: null })
      setDraft(initial)
      setHistory([initial])
      setHistoryIndex(0)
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

  // Keyboard undo/redo
  useEffect(() => {
    function handleKeyDown(e) {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target?.tagName)) return
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault()
        if (e.shiftKey) {
          if (historyIndex < history.length - 1) {
            setDraft(history[historyIndex + 1])
            setHistoryIndex(historyIndex + 1)
            setSaveState({ status: 'idle', message: null })
            setReviewComplete(false)
            setApproveLayout(false)
          }
        } else if (historyIndex > 0) {
          setDraft(history[historyIndex - 1])
          setHistoryIndex(historyIndex - 1)
          setSaveState({ status: 'idle', message: null })
          setReviewComplete(false)
          setApproveLayout(false)
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
        e.preventDefault()
        if (historyIndex < history.length - 1) {
          setDraft(history[historyIndex + 1])
          setHistoryIndex(historyIndex + 1)
          setSaveState({ status: 'idle', message: null })
          setReviewComplete(false)
          setApproveLayout(false)
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [historyIndex, history])

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

  function pushDraft(nextDraft, { wallChange = false } = {}) {
    setHistory((prev) => [...prev.slice(0, historyIndex + 1), nextDraft])
    setHistoryIndex((prev) => prev + 1)
    setDraft(nextDraft)
    setSaveState({ status: 'idle', message: null })
    setReviewComplete(false)
    setApproveLayout(false)
    if (wallChange && nextDraft.rooms.some((r) => r.id.startsWith('room-') && r.disposition !== 'rejected')) {
      setStaleRoomsWarning(true)
    }
  }

  function handleUndo() {
    if (historyIndex > 0) {
      const prev = history[historyIndex - 1]
      setHistoryIndex(historyIndex - 1)
      setDraft(prev)
      setSaveState({ status: 'idle', message: null })
      setReviewComplete(false)
      setApproveLayout(false)
    }
  }

  function handleRedo() {
    if (historyIndex < history.length - 1) {
      const next = history[historyIndex + 1]
      setHistoryIndex(historyIndex + 1)
      setDraft(next)
      setSaveState({ status: 'idle', message: null })
      setReviewComplete(false)
      setApproveLayout(false)
    }
  }

  function handleAddWall({ start, end, estimated_thickness_pixels }) {
    const id = nextManualId(draft.walls, 'manual-wall')
    const newWall = {
      id,
      disposition: 'accepted',
      start,
      end,
      estimated_thickness_pixels: estimated_thickness_pixels || 12,
    }
    const nextWalls = [...draft.walls, newWall]
    pushDraft({ ...draft, walls: nextWalls }, { wallChange: true })
    setSelected({ kind: 'wall', id })
    setLayers((cur) => ({ ...cur, walls: true }))
  }

  function handleUpdateWall(updated) {
    const nextWalls = draft.walls.map((w) => w.id === updated.id ? updated : w)
    pushDraft({ ...draft, walls: nextWalls }, { wallChange: true })
  }

  function handleDeleteWall(wallId) {
    const nextWalls = draft.walls.map((w) => w.id === wallId ? { ...w, disposition: 'rejected' } : w)
    pushDraft({ ...draft, walls: nextWalls }, { wallChange: true })
    if (selected?.id === wallId) setSelected(null)
  }

  function excludeStaleRooms() {
    const nextRooms = draft.rooms.map((r) => r.id.startsWith('room-') ? { ...r, disposition: 'rejected' } : r)
    pushDraft({ ...draft, rooms: nextRooms })
    setStaleRoomsWarning(false)
  }

  function updateSelected(replacement) {
    if (!selected) return
    const key = `${selected.kind}s`
    const isWall = selected.kind === 'wall'
    const nextDraft = {
      ...draft,
      [key]: draft[key].map((item) => item.id === selected.id ? replacement : item),
    }
    pushDraft(nextDraft, { wallChange: isWall })
  }

  function updateRoom(room) {
    const nextRooms = draft.rooms.map((item) => item.id === room.id ? room : item)
    pushDraft({ ...draft, rooms: nextRooms })
  }

  function addEntity(kind) {
    const plane = state.record.candidate.payload.source_plane
    const center = { x: Math.round(plane.width_pixels / 2), y: Math.round(plane.height_pixels / 2) }
    const radius = Math.min(50, plane.width_pixels / 4, plane.height_pixels / 4)
    const key = `${kind}s`
    const prefix = `manual-${kind}`
    const id = nextManualId(draft[key], prefix)
    const entity = kind === 'wall'
      ? { id, disposition: 'accepted', start: { x: center.x - radius, y: center.y }, end: { x: center.x + radius, y: center.y }, estimated_thickness_pixels: 12 }
      : kind === 'room'
        ? { id, disposition: 'accepted', name: null, boundary: [
            { x: center.x - radius, y: center.y - radius }, { x: center.x + radius, y: center.y - radius },
            { x: center.x + radius, y: center.y + radius }, { x: center.x - radius, y: center.y + radius },
          ] }
        : { id, disposition: 'accepted', center, symbol_legend_id: null }
    pushDraft({ ...draft, [key]: [...draft[key], entity] }, { wallChange: kind === 'wall' })
    setSelected({ kind, id })
    setLayers((current) => ({ ...current, [`${kind}s`]: true }))
    setView('2d')
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
        evidence_notes: notes.trim() || (draftOnly ? 'Unfinished wall-first review draft. Not approved for canonical layout.' : ''),
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
  const activeWallsCount = draft.walls.filter((item) => item.disposition !== 'rejected').length
  const activeRoomsCount = draft.rooms.filter((item) => item.disposition !== 'rejected').length

  return (
    <article className="detection-review-page demo-review-page">
      <a className="detection-back-link" href={getProjectHref(projectId)}>← Back to project</a>
      <nav className="demo-steps" aria-label="Floor-plan workflow">
        <a href={getProjectHref(projectId)}>1 · Upload &amp; analyze</a>
        <strong aria-current="step">2 · Edit walls in 2D / 3D</strong>
        <a href="#demo-approval-title" onClick={(event) => { event.preventDefault(); document.getElementById('demo-approval-title')?.scrollIntoView({ behavior: 'smooth' }) }}>3 · Save &amp; approve when ready</a>
      </nav>
      <header className="detection-review-header">
        <div>
          <span className="mono">LOCAL DEMO REVIEW · JOB #{processingJobId}</span>
          <h1>Correct floor-plan proposals</h1>
        </div>
        <p>{activeWallsCount} wall segments · {activeRoomsCount} room proposals</p>
      </header>
      <p role="note">
        Walls are traced from thick structural boundaries and partitions. Thin grids, wiring, troffers, and dimensions are rejected. Verify or draw walls in 2D before 3D preview.
      </p>
      {truncated.length > 0 && <p className="detection-limit-warning" role="alert">Bounded proposal cap reached for: {truncated.join(', ')}. Add missing geometry manually where needed.</p>}
      {state.legends.length === 0 && <details><summary>Do I need a symbol legend?</summary><p>Not for wall review or 3D preview. Electrical-symbol approval requires an approved VED legend.</p></details>}

      <section className="demo-preview-workspace" aria-label="Wall-first workspace">
        {/* Workspace Toolbar matching reference */}
        <div className="demo-workspace-toolbar">
          <div className="demo-tool-group" role="group" aria-label="Wall editing tools">
            <button
              type="button"
              className={`demo-tool-btn ${tool === 'move' ? 'is-active' : ''}`}
              onClick={() => setTool('move')}
              aria-pressed={tool === 'move'}
              title="Move Walls / Drag Endpoints"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="5 9 2 12 5 15" /><polyline points="9 5 12 2 15 5" /><polyline points="15 19 12 22 9 19" /><polyline points="19 9 22 12 19 15" /><line x1="2" y1="12" x2="22" y2="12" /><line x1="12" y1="2" x2="12" y2="22" />
              </svg>
              Move Walls
            </button>
            <button
              type="button"
              className={`demo-tool-btn ${tool === 'draw' ? 'is-active' : ''}`}
              onClick={() => setTool('draw')}
              aria-pressed={tool === 'draw'}
              title="Draw Walls (Click-to-start / Click-to-finish, Esc to cancel)"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
              </svg>
              Draw Walls
            </button>
            <button
              type="button"
              className={`demo-tool-btn ${tool === 'delete' ? 'is-active' : ''}`}
              onClick={() => setTool('delete')}
              aria-pressed={tool === 'delete'}
              title="Delete Walls (Click wall to delete or press Del key)"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
              Delete Walls
            </button>
          </div>

          <div className="demo-history-group" role="group" aria-label="History">
            <button
              type="button"
              className="demo-icon-btn"
              onClick={handleUndo}
              disabled={historyIndex <= 0}
              title="Undo (Ctrl+Z)"
            >
              Undo
            </button>
            <button
              type="button"
              className="demo-icon-btn"
              onClick={handleRedo}
              disabled={historyIndex >= history.length - 1}
              title="Redo (Ctrl+Y)"
            >
              Redo
            </button>
          </div>

          <div className="demo-blueprint-controls">
            <button
              type="button"
              className="demo-icon-btn"
              onClick={() => setLayers((cur) => ({ ...cur, source: !cur.source }))}
            >
              {layers.source ? 'Hide Blueprint' : 'Show Blueprint'}
            </button>
            {layers.source && (
              <label className="demo-opacity-label">
                Opacity
                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.05"
                  value={blueprintOpacity}
                  onChange={(e) => setBlueprintOpacity(Number(e.target.value))}
                />
              </label>
            )}
          </div>

          <div className="demo-view-switch" role="group" aria-label="Preview mode">
            <button type="button" aria-pressed={view === '2d'} onClick={() => setView('2d')} aria-label="2D · Review rooms">2D</button>
            <button type="button" aria-pressed={view === '3d'} onClick={() => setView('3d')} aria-label="3D · Draft preview">3D</button>
          </div>

          <button
            type="button"
            className="demo-done-btn"
            disabled={saveState.status === 'saving'}
            onClick={() => saveReview({ draftOnly: true })}
            title="Save draft review"
            aria-label="Save unfinished draft"
          >
            Done »
          </button>
        </div>

        {staleRoomsWarning && (
          <div className="demo-stale-rooms-banner" role="alert">
            <span>Wall edits invalidate automatic room boundaries. Review room corners or proceed with a walls-only layout.</span>
            <button type="button" className="btn-stale-dismiss" onClick={excludeStaleRooms}>Exclude stale room polygons</button>
          </div>
        )}

        <p className="demo-next-step">
          {view === '2d'
            ? 'Walls are shown as centerlines with estimated thickness. Drag wall endpoints to resize, drag wall bodies to move, or switch to Draw Walls to add new walls. Hold Shift for 90° constraint.'
            : 'Illustrative 3D preview of current wall geometry. Return to 2D to adjust walls at any time.'}
        </p>

        {view === '2d' ? (
          <>
            <div className="demo-layer-controls">
              <label>
                <input type="checkbox" checked={layers.walls} onChange={(e) => setLayers((c) => ({ ...c, walls: e.target.checked }))} />
                Show walls (default)
              </label>
              <label>
                <input type="checkbox" checked={layers.rooms} onChange={(e) => setLayers((c) => ({ ...c, rooms: e.target.checked }))} />
                Show room proposals (optional)
              </label>
              <label>
                <input type="checkbox" checked={layers.symbols} onChange={(e) => setLayers((c) => ({ ...c, symbols: e.target.checked }))} />
                Show symbol proposals (optional)
              </label>
              <label>
                <input type="checkbox" checked={layers.source} onChange={(e) => setLayers((c) => ({ ...c, source: e.target.checked }))} />
                Show original blueprint
              </label>
            </div>
            {draft.walls.length === 0 && (
              <p role="status">No walls detected. Click &quot;Draw Walls&quot; above to draw walls directly over the blueprint.</p>
            )}
            <DemoInterpretationCanvas
              image={state.image}
              width={plane.width_pixels}
              height={plane.height_pixels}
              draft={draft}
              selected={selected}
              onSelect={setSelected}
              layers={layers}
              tool={tool}
              onToolChange={setTool}
              onAddWall={handleAddWall}
              onUpdateWall={handleUpdateWall}
              onDeleteWall={handleDeleteWall}
              onUpdateRoom={updateRoom}
              blueprintOpacity={blueprintOpacity}
            />
          </>
        ) : (
          <Suspense fallback={<p role="status">Opening draft 3D preview…</p>}>
            <DraftRoomPreview draft={draft} width={plane.width_pixels} height={plane.height_pixels} projectId={projectId} />
          </Suspense>
        )}
        {saveState.message && <p role={saveState.status === 'error' ? 'alert' : 'status'}>{saveState.message}</p>}
      </section>

      <section className="demo-review-tools" aria-labelledby="demo-tools-title" hidden={view !== '2d'}>
        <h2 id="demo-tools-title">Review and inspect</h2>
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
            {['wall', 'room', 'symbol'].filter((kind) => layers[`${kind}s`]).flatMap((kind) => draft[`${kind}s`].map((item) => <option key={`${kind}:${item.id}`} value={`${kind}:${item.id}`}>{kind} · {item.name || item.id} · {item.disposition === 'rejected' ? 'excluded' : 'in draft'}</option>))}
          </select>
        </label>
        {selectedEntity && <div className="demo-selected-editor">
          <h3>{selected.kind} {selectedEntity.id}</h3>
          <label>Review decision
            <select value={selectedEntity.disposition} onChange={(event) => updateSelected({ ...selectedEntity, disposition: event.target.value })}>
              <option value="accepted">Accept</option><option value="rejected">Reject</option>
            </select>
          </label>
          {selected.kind === 'wall' && (
            <>
              <NumericPoint label="Start point" value={selectedEntity.start} onChange={(start) => updateSelected({ ...selectedEntity, start })} />
              <NumericPoint label="End point" value={selectedEntity.end} onChange={(end) => updateSelected({ ...selectedEntity, end })} />
              <button type="button" className="btn btn-outline-danger" onClick={() => handleDeleteWall(selectedEntity.id)}>Delete wall</button>
            </>
          )}
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
