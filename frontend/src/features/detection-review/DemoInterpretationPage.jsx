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
import { Button } from '../../components/ui/button.jsx'
import { Box, Layers3, Undo2, Redo2, Save, Trash2 } from 'lucide-react'
import { ReviewToolRail } from './ReviewToolRail.jsx'
import { repairDraftWalls } from './repairDraftWalls.js'
import { clampDevicePoint, describeReviewSymbol, reviewGeometryPayload } from './devicePresentation.js'

const DraftRoomPreview = lazy(() => import('./DraftRoomPreview.jsx').then((module) => ({ default: module.DraftRoomPreview })))


function decodeImage(url) {
  return new Promise((resolve, reject) => {
    const image = new window.Image()
    image.onload = () => resolve(image)
    image.onerror = reject
    image.src = url
  })
}

const EXPERIMENTAL_SYMBOL_PROVIDERS = new Set([
  'experimental_pull_station_template',
  'experimental_reviewed_symbol_yolo',
  'experimental_linked_legend_yolo',
  'development_multiclass56_yolo',
])


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
      disposition: 'unresolved',
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
  const [layers, setLayers] = useState({ walls: true, rooms: false, symbols: true, names: true, source: true })
  const [tool, setTool] = useState('select')
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
      if (EXPERIMENTAL_SYMBOL_PROVIDERS.has(record.candidate.provenance?.model_release_id)) {
        setLayers((current) => ({ ...current, symbols: true }))
      }
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
  const presentations = useMemo(() => draft && state.record
    ? Object.fromEntries(draft.symbols.map((symbol) => [symbol.id, describeReviewSymbol(symbol, state.record, state.legends)])) : {},
  [draft, state.record, state.legends])

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

  function updateSymbol(symbol) {
    const plane = state.record.candidate.payload.source_plane
    const center = clampDevicePoint(symbol.center, plane.width_pixels, plane.height_pixels)
    if (!center) return
    pushDraft({ ...draft, symbols: draft.symbols.map((item) => item.id === symbol.id ? { ...symbol, center } : item) })
  }

  function removeSymbol(id) {
    pushDraft({ ...draft, symbols: draft.symbols.map((item) => item.id === id ? { ...item, disposition: 'rejected' } : item) })
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
        : { id, disposition: 'unresolved', center, symbol_legend_id: null }
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
        // Preserve review layers not edited by this workspace; never silently erase them.
        ...Object.fromEntries(['openings', 'panels', 'scale_evidence', 'observed_wiring', 'checklist']
          .filter((key) => state.record.review?.[key] != null).map((key) => [key, state.record.review[key]])),
        ...reviewGeometryPayload(draft),
      })
      setState((current) => ({ ...current, record }))
      const savedDraft = initialDraft(record)
      setDraft(savedDraft)
      setHistory((previous) => [...previous.slice(0, historyIndex), savedDraft, ...previous.slice(historyIndex + 1)])
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
  const experimentalProvider = state.record.candidate.provenance?.model_release_id
  const experimental = experimentalProvider === 'experimental_pull_station_template'
  const trained = experimentalProvider === 'experimental_reviewed_symbol_yolo'
  const linked = experimentalProvider === 'experimental_linked_legend_yolo'
  const general = experimentalProvider === 'development_multiclass56_yolo'
  const truncated = ['walls', 'rooms', 'symbols'].filter(
    (key) => state.record.candidate.payload[key].truncated,
  )
  const activeWallsCount = draft.walls.filter((item) => item.disposition !== 'rejected').length
  const activeRoomsCount = draft.rooms.filter((item) => item.disposition !== 'rejected').length

  return (
    <article className="detection-review-page demo-review-page studio-review-page">
      <a className="detection-back-link" href={getProjectHref(projectId)}>← Back to project</a>
      <nav className="demo-steps" aria-label="Floor-plan workflow">
        <a href={getProjectHref(projectId)}>1 · Upload &amp; analyze</a>
        <strong aria-current="step">2 · Edit plan &amp; devices in 2D / 3D</strong>
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
      {experimental && <p role="note">Experimental Pull station template proposals only (two Group 7 source templates; page scale selected from 1.0/1.2 using interior matches). The second page was used for tuning, not held-out evaluation. Orange review overlays are unconfirmed; match similarity is not calibrated confidence. Inspect the original image, then accept, correct, reject, or add symbols. Map accepted symbols to an approved VED legend. Other classes remain unresolved.</p>}
      {general && <p role="note">One shared supervised development detector includes all 56 eligible drawing-legend entries. Inclusion is not a guarantee of detection. Scarce examples and conflicting labels limit results; scores are not calibrated and independent accuracy is unverified. Proposals start unresolved. Inspect, accept, correct, reject, or add symbols, then map accepted symbols to the approved drawing legend and save your draft.</p>}
      {(trained || linked) && <p role="note">Experimental trained symbol proposals are unresolved until you inspect, correct, and map them to the drawing's approved VED legend. {linked ? 'This five-class linked-legend model has uneven same-source recall and text/grid mistakes.' : 'This narrower model covers troffer, smoke detector, and Pull station only.'} Detector scores are not calibrated confidence; no independent-project accuracy or production approval is claimed.</p>}
      {truncated.length > 0 && <p className="detection-limit-warning" role="alert">Bounded proposal cap reached for: {truncated.join(', ')}. Add missing geometry manually where needed.</p>}
      {state.legends.length === 0 && <details><summary>Do I need a symbol legend?</summary><p>Not for wall review or 3D preview. Electrical-symbol approval requires an approved VED legend.</p></details>}

      <div className="studio-review-headerbar">
        <div className="studio-review-mode" role="group" aria-label="Preview mode">
          <Button variant={view === '2d' ? 'secondary' : 'ghost'} size="sm" aria-pressed={view === '2d'} aria-label="2D · Review rooms" onClick={() => setView('2d')}><Layers3 aria-hidden="true" />Edit 2D</Button>
          <Button variant={view === '3d' ? 'secondary' : 'ghost'} size="sm" aria-pressed={view === '3d'} aria-label="3D · Draft preview" onClick={() => { setView('3d'); setTool('select') }}><Box aria-hidden="true" />View 3D</Button>
        </div>
        <span className="mono studio-draft-status">SHARED DRAFT · {draft.symbols.filter((item) => item.disposition !== 'rejected').length} DEVICES</span>
        <Button variant="ghost" size="icon" aria-label="Undo" disabled={historyIndex <= 0} onClick={handleUndo}><Undo2 aria-hidden="true" /></Button>
        <Button variant="ghost" size="icon" aria-label="Redo" disabled={historyIndex >= history.length - 1} onClick={handleRedo}><Redo2 aria-hidden="true" /></Button>
        <Button size="sm" disabled={saveState.status === 'saving'} aria-label="Save unfinished draft" onClick={() => saveReview({ draftOnly: true })}><Save aria-hidden="true" />Save draft</Button>
      </div>
      <div className="studio-review-workbench studio-device-workbench">
      <ReviewToolRail view={view} tool={tool} onToolChange={setTool} onAdd={addEntity} layers={layers} setLayers={setLayers} opacity={blueprintOpacity} onOpacityChange={setBlueprintOpacity}
        onConnectWalls={() => {
          const result = repairDraftWalls(draft.walls, plane.width_pixels, plane.height_pixels)
          if (result.joined || result.merged) pushDraft({ ...draft, walls: result.walls }, { wallChange: true })
          setSaveState({ status: 'idle', message: `Wall repair: ${result.joined} endpoints connected, ${result.merged} overlapping segments merged. Gaps up to ${Math.round(result.maxGap)} px checked; doorway gaps preserved. Review the blueprint, then save draft. Undo is available.` })
        }} />
      <section className="demo-preview-workspace" aria-label="Wall-first workspace">

        {staleRoomsWarning && (
          <div className="demo-stale-rooms-banner" role="alert">
            <span>Wall edits invalidate automatic room boundaries. Review room corners or proceed with a walls-only layout.</span>
            <button type="button" className="btn-stale-dismiss" onClick={excludeStaleRooms}>Exclude stale room polygons</button>
          </div>
        )}

        <p className="demo-next-step">
          {view === '2d'
            ? 'Walls are shown as centerlines with estimated thickness. Drag wall endpoints to resize, drag wall bodies to move, or switch to Draw Walls to add new walls. Hold Shift for 90° constraint.'
            : 'Select or drag a device in 3D. Classify and remove it in the inspector. Walls use the same 2D draft; no real mounting heights are assumed.'}
        </p>

        {view === '2d' ? (
          <>

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
              onUpdateSymbol={updateSymbol}
              onDeleteSymbol={removeSymbol}
              presentations={presentations}
              blueprintOpacity={blueprintOpacity}
            />
          </>
        ) : (
          <Suspense fallback={<p role="status">Opening draft 3D preview…</p>}>
            <DraftRoomPreview draft={draft} layers={layers} width={plane.width_pixels} height={plane.height_pixels} projectId={projectId}
              presentations={presentations} selected={selected} onSelect={setSelected} onUpdateSymbol={updateSymbol} navigationMode={tool} />
          </Suspense>
        )}
        {saveState.message && <p role={saveState.status === 'error' ? 'alert' : 'status'}>{saveState.message}</p>}
      </section>

      <section className="demo-review-tools" aria-labelledby="demo-tools-title">
        <h2 id="demo-tools-title">Review and inspect</h2>

        <label>Select proposal
          <select value={selected ? `${selected.kind}:${selected.id}` : ''} onChange={(event) => {
            const [kind, id] = event.target.value.split(':')
            setSelected(event.target.value ? { kind, id } : null)
            if (event.target.value) setLayers((current) => ({ ...current, [`${kind}s`]: true }))
          }}>
            <option value="">Choose an item</option>
            {['symbol', 'wall', 'room'].flatMap((kind) => draft[`${kind}s`].map((item) => <option key={`${kind}:${item.id}`} value={`${kind}:${item.id}`}>{kind === 'symbol' ? presentations[item.id].label : item.name || `${kind} ${item.id}`} · {item.disposition === 'rejected' ? 'removed' : item.disposition} · {item.id}</option>))}
          </select>
        </label>
        {selectedEntity && <div className="demo-selected-editor">
          <h3>{selected.kind === 'symbol' ? presentations[selectedEntity.id].name : `${selected.kind} ${selectedEntity.id}`}</h3>
          {selected.kind === 'symbol' && <p className="studio-device-provenance"><span className="mono">{selectedEntity.id}</span><br />{presentations[selectedEntity.id].mapped ? 'Legend linked · review decision remains separate' : 'Unmapped proposal · choose an approved legend below'}<br />Original detection: {presentations[selectedEntity.id].originalLabel}</p>}
          <label>Review decision
            <select value={selectedEntity.disposition} onChange={(event) => updateSelected({ ...selectedEntity, disposition: event.target.value })}>
              <option value="unresolved">Unresolved</option><option value="accepted">Accept</option><option value="corrected">Corrected</option><option value="added">Manually added</option><option value="rejected">Reject</option>
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
            <NumericPoint label="Symbol center (source pixels)" value={selectedEntity.center} onChange={(center) => updateSymbol({ ...selectedEntity, center })} />
            <label>Approved VED legend class<select value={selectedEntity.symbol_legend_id || ''} onChange={(event) => updateSelected({ ...selectedEntity, symbol_legend_id: event.target.value ? Number(event.target.value) : null })}>
              <option value="">Unmapped</option>{state.legends.map((legend) => <option key={legend.id} value={legend.id}>{legend.class_id} — {legend.name}</option>)}
            </select></label>
            <p className="studio-device-provenance">Drag this device in either view, or edit X/Y. Mounting height and physical dimensions are not yet recorded.</p>
            <Button variant="outline" className="studio-remove-device" disabled={selectedEntity.disposition === 'rejected'} onClick={() => removeSymbol(selectedEntity.id)}><Trash2 aria-hidden="true" />Remove device</Button>
          </>}
        </div>}
        {!selectedEntity && <p className="studio-inspector-empty">Select a named device in the canvas or list to move, classify or remove it. Changes stay in the shared draft until saved.</p>}
      </section>

      </div>
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
