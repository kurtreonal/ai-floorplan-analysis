import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { useUserPreferences } from '../settings/useUserPreferences.js'
import { ViewportFrame } from '../../components/ViewportFrame.jsx'
import { WorkspacePanel } from '../../components/WorkspacePanel.jsx'

import {
  DemoInterpretationApiError,
  fetchDemoInterpretation,
  saveDemoLayout,
  saveDemoReview,
} from '../../api/demoInterpretation.js'
import { fetchCurrentLayout, LayoutApiError } from '../../api/layouts.js'
import { fetchReviewImage } from '../../api/reviewImages.js'
import { fetchSymbolLegends, isWiringLegend } from '../../api/symbolLegends.js'
import { groupLegendChoices } from '../../api/legendChoices.js'
import {
  getLayoutHref,
  getProjectHref,
  getViewer3dHref,
} from '../../routes/projectRoutes.js'
import { DemoInterpretationCanvas } from './DemoInterpretationCanvas.jsx'
import { SourceViewsPanel } from './SourceViewsPanel.jsx'
import { ObservedWiringPanel } from './ObservedWiringPanel.jsx'
import { WireDeviceConnections } from './WireDeviceConnections.jsx'
import { BOMPanel } from '../estimation/BOMPanel.jsx'
import { initialWiringDraft, wiringSavePayload } from './observedWiringDraft.js'
import { withWiringMethod } from './wireDrawing.js'
import { connectTouchingWireEndpoints, detachDevice, moveConnectedDevice, moveConnectedWirePoint } from './deviceConnections.js'
import './detectionReview.css'
import { Button } from '../../components/ui/button.jsx'
import { Box, Layers3, Undo2, Redo2, Save, Trash2 } from 'lucide-react'
import { ReviewToolRail } from './ReviewToolRail.jsx'
import { orderNamed } from '../../utils/listOrder.js'
import { autoLinkSymbols, clampDevicePoint, describeReviewSymbol, relatedSymbolIds, updateRelatedSymbols, reviewGeometryPayload } from './devicePresentation.js'
import { addConnectedWall, moveConnectedWall, deleteConnectedWall } from './wallDrawing.js'
import { WallDimensionEditor } from './WallDimensionEditor.jsx'
import { pastedDevice, useDeviceClipboard } from './useDeviceClipboard.js'
import { WireJunctionEditor } from './WireJunctionEditor.jsx'
import { WiringRecoveryStatus } from './WiringRecoveryStatus.jsx'
import { updateWireNetwork, applyWireEdits } from './wireJunctions.js'
import { DevicePicker } from './DevicePicker.jsx'
import { commitWiringPath } from './connectedWiring.js'
import { ObjectBrowser } from './ObjectBrowser.jsx'

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


function initialDraft(record, legends = []) {
  const draft = rawInitialDraft(record,legends)
  draft.openings=structuredClone(record.review?.openings??record.draft_review?.openings??[])
  draft.source_openings=(record.candidate.payload.openings?.items??[]).map(o=>({id:o.id,points:[o.start,o.end]}))
  if (record.review?.approved_for_layout) return draft
  return connectTouchingWireEndpoints(draft,Object.fromEntries(draft.symbols.map(s =>
    [s.id,describeReviewSymbol(s,record,legends)])))
}

function rawInitialDraft(record, legends = []) {
  if (record.review) {
    return {
      walls: record.review.walls,
      rooms: record.review.rooms,
      wirings: initialWiringDraft(record),
      symbols: autoLinkSymbols(record.review.symbols.map((symbol) => ({
        id: symbol.id,
        disposition: symbol.disposition,
        center: symbol.center,
        symbol_legend_id: symbol.symbol_legend_id,
        custom_unit_price: symbol.custom_unit_price ?? null,
        mounting_height_meters: symbol.mounting_height_meters ?? null,
        mounting_wall_id: symbol.mounting_wall_id ?? null,
        ...(symbol.gang_count_confirmed ? {gang_count_confirmed:true} : {}),
      })),record,legends),
    }
  }
  const payload = record.candidate.payload
  return {
    wirings: initialWiringDraft(record),
    walls: record.draft_review?.walls ?? record.draft_walls ?? payload.walls.items.map((item) => ({
      id: item.id,
      disposition: 'accepted',
      start: item.start,
      end: item.end,
      estimated_thickness_pixels: item.estimated_thickness_pixels ?? 12,
    })),
    rooms: record.draft_review?.rooms ?? payload.rooms.items.map((item) => ({
      id: item.id,
      disposition: 'accepted',
      name: item.label,
      boundary: item.boundary,
    })),
    symbols: autoLinkSymbols(record.draft_review?.symbols ?? payload.symbols.items.map((item) => ({
      id: item.id,
      disposition: 'unresolved',
      center: item.center,
      symbol_legend_id: null,
    })),record,legends),
  }
}


function errorMessage(error) {
  if (error?.status === 401) return null
  if (error?.code === 'SYMBOL_MAPPING_REQUIRED') return 'Map every accepted symbol to an approved VED legend class before completing review.'
  if (error?.code === 'PROVISIONAL_SWITCH_COUNT_REQUIRES_CORRECTION') return 'Correct the provisional switch gang count before final approval. You can still save an unfinished draft.'
  if (error?.code === 'METRIC_INPUTS_UNRESOLVED') return 'Approve the exact page scale and floor elevation from the project page first.'
  if (error?.code === 'SCALE_REFERENCE_MISMATCH') return 'The approved scale dimensions do not match this normalized page. Review the scale again.'
  if (error?.code === 'STALE_REVIEW_REVISION') return 'A newer review revision exists. Reload before saving.'
  if (error?.code === 'STALE_INTERPRETATION_RUN') return 'This analysis has been superseded. Open the latest result from the project to edit and save; this historical result stays preserved.'
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


export function DemoInterpretationPage({ projectId, projectFloorId, floorPlanId, processingJobId, session }) {
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
  const [opened3d, setOpened3d] = useState(false)
  // Default to wall-focused view with rooms hidden
  const { preferences } = useUserPreferences()
  const [layers, setLayers] = useState(() => ({ walls: preferences.walls, rooms: false, symbols: preferences.symbols, names: false, dimensions: false, wirings: preferences.wiring, source: preferences.blueprint }))
  const [tool, setTool] = useState('select')
  const [placementLegendId, setPlacementLegendId] = useState('')
  const [drawingWireMethod, setDrawingWireMethod] = useState('concealed_in_ceiling')
  const [drawingPending,setDrawingPending] = useState(false)
  const [editingSession, setEditingSession] = useState(0)
  const [analysisRegion, setAnalysisRegion] = useState(null)
  const [blueprintOpacity, setBlueprintOpacity] = useState(1.0)
  const [history, setHistory] = useState([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [staleRoomsWarning, setStaleRoomsWarning] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    let objectUrl = null
    Promise.all([
      fetchDemoInterpretation(floorPlanId, { signal: controller.signal, processingJobId }),
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
      const initial = initialDraft(record,legends)
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
      if (e.target?.closest?.('input, textarea, select, [contenteditable]:not([contenteditable="false"])') || saveState.status === 'saving') return
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        setDrawingPending(false)
        e.preventDefault()
        setEditingSession(value=>value+1)
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
        setDrawingPending(false)
        e.preventDefault()
        setEditingSession(value=>value+1)
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
  }, [historyIndex, history, saveState.status])

  useDeviceClipboard({
    sourceKey: `${floorPlanId}:${processingJobId}`,
    draft, selected, plane: state.record?.candidate.payload.source_plane,
    disabled: state.status !== 'ready' || saveState.status === 'saving' || drawingPending,
    onPaste(snapshot) {
      const symbol = pastedDevice(snapshot, draft, state.record.candidate.payload.source_plane,
        nextManualId(draft.symbols, 'manual-symbol'))
      if (!symbol) return
      pushDraft({ ...draft, symbols: [...draft.symbols, symbol] }, { autoConnect: false })
      setEditingSession(value => value + 1)
      setSelected({ kind: 'symbol', id: symbol.id })
      setTool('select')
      setLayers(current => ({ ...current, symbols: true }))
    },
  })


  const selectedEntity = useMemo(() => (
    selected && draft ? draft[`${selected.kind}s`].find((item) => item.id === selected.id && item.disposition !== 'rejected') : null
  ), [draft, selected])
  const presentations = useMemo(() => draft && state.record
    ? Object.fromEntries(draft.symbols.map((symbol) => [symbol.id, describeReviewSymbol(symbol, state.record, state.legends)])) : {},
  [draft, state.record, state.legends])

  const savedReviewMatches = Boolean(state.record?.review
    && JSON.stringify(draft) === JSON.stringify(initialDraft(state.record,state.legends))
    && notes.trim() === state.record.review.evidence_notes
    && reviewComplete === state.record.review.review_complete
    && approveLayout === state.record.review.approved_for_layout
    && (approveLayout ? Number(wallThickness) : null) === state.record.review.wall_thickness_meters
    && (approveLayout ? Number(wallHeight) : null) === state.record.review.wall_height_meters)

  function pushDraft(nextDraft, { wallChange = false, autoConnect = true } = {}) {
    if (saveState.status === 'saving' || nextDraft === draft) return
    if (selected && !nextDraft[`${selected.kind}s`]?.some(item => item.id === selected.id && item.disposition !== 'rejected')) setSelected(null)
    const nextPresentations = Object.fromEntries(nextDraft.symbols.map(s => [s.id, describeReviewSymbol(s,state.record,state.legends)]))
    if (autoConnect) nextDraft = connectTouchingWireEndpoints(nextDraft,nextPresentations)
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
    setDrawingPending(false)
    if (historyIndex > 0) {
      setEditingSession(value=>value+1)
      const prev = history[historyIndex - 1]
      setHistoryIndex(historyIndex - 1)
      setDraft(prev)
      setSaveState({ status: 'idle', message: null })
      setReviewComplete(false)
      setApproveLayout(false)
    }
  }

  function handleRedo() {
    setDrawingPending(false)
    if (historyIndex < history.length - 1) {
      setEditingSession(value=>value+1)
      const next = history[historyIndex + 1]
      setHistoryIndex(historyIndex + 1)
      setDraft(next)
      setSaveState({ status: 'idle', message: null })
      setReviewComplete(false)
      setApproveLayout(false)
    }
  }

  function handleAddWall(wall) {
    if(saveState.status==='saving')return false
    let next
    try {next=addConnectedWall(draft,wall)}catch(error){setSaveState({status:'error',message:error.message});return false}
    if(next===draft)return false
    pushDraft(next, { wallChange: true })
    setSelected({ kind: 'wall', id:next.walls.at(-1).id })
    setLayers((cur) => ({ ...cur, walls: true }))
    return true
  }

  function handleUpdateWall(updated,options) {
    if(saveState.status==='saving')return
    try {
      updated={...updated,disposition:updated.disposition==='added'?'added':'corrected'}
      const next=moveConnectedWall(draft,updated,options)
      const plane=state.record.candidate.payload.source_plane
      if(next.walls.some(w=>w.disposition!=='rejected'&&[w.start,w.end].some(p=>p.x<0||p.y<0||p.x>plane.width_pixels||p.y>plane.height_pixels)))throw new Error('Wall edit would leave the source page.')
      if(next.symbols.some(s=>s.disposition!=='rejected'&&(s.center.x<0||s.center.y<0||s.center.x>plane.width_pixels||s.center.y>plane.height_pixels)))throw new Error('Wall edit would move a mounted device outside the source page.')
      pushDraft(next, { wallChange: true })
    }catch(error){setSaveState({status:'error',message:error.message})}
  }

  function handleDeleteWall(wallId, detachMounted = false) {
    if(saveState.status==='saving')return
    try {pushDraft(deleteConnectedWall(draft,wallId,{detachMounted}), { wallChange: true })}
    catch(error){setSelected({kind:'wall',id:wallId});setSaveState({status:'error',message:error.message});return}
    if (detachMounted) setSaveState({status:'idle',message:'Devices kept in place. Select a device to choose its new mounting wall.'})
    if (selected?.id === wallId) setSelected(null)
  }

  function excludeStaleRooms() {
    const nextRooms = draft.rooms.map((r) => r.id.startsWith('room-') ? { ...r, disposition: 'rejected' } : r)
    pushDraft({ ...draft, rooms: nextRooms })
    setStaleRoomsWarning(false)
  }

  function updateSelected(replacement) {
    if (!selected) return
    if(selected.kind==='wall'){handleUpdateWall(replacement);return}
    if (selected.kind === 'wiring') {
      editWireNetwork(current => updateWireNetwork(current, {...replacement,
        ...(replacement.origin === 'generated' ? {suppression_reason:null} : {}),
        disposition: replacement.disposition === 'rejected' || replacement.disposition === 'added' ? replacement.disposition : 'corrected'}))
      return
    }
    const key = `${selected.kind}s`
    const isWall = selected.kind === 'wall'
    const nextDraft = {
      ...draft,
      [key]: draft[key].map((item) => item.id === selected.id ? replacement : item),
    }
    pushDraft(nextDraft, { wallChange: isWall })
  }

  function updateDeviceType(patch) {
    if (selected?.kind !== 'symbol') return
    pushDraft({...draft,symbols:updateRelatedSymbols(draft.symbols,selected.id,state.record,patch)})
  }

  function updateRoom(room) {
    const nextRooms = draft.rooms.map((item) => item.id === room.id ? room : item)
    pushDraft({ ...draft, rooms: nextRooms })
  }

  function updateSymbol(symbol, snap = null) {
    if (saveState.status === 'saving') return false
    const plane = state.record.candidate.payload.source_plane
    const center = clampDevicePoint(symbol.center, plane.width_pixels, plane.height_pixels)
    if (!center) return false
    const next = moveConnectedDevice(draft, {...symbol, center}, snap)
    if (next === draft) return false
    pushDraft(next)
    return true
  }

  function removeSymbol(id) {
    pushDraft({ ...detachDevice(draft, id), symbols: draft.symbols.map((item) => item.id === id ? { ...item, disposition: 'rejected' } : item) })
  }

  function moveWirePoint(id, index, point, snap = null) {
    if (saveState.status === 'saving') return
    const plane = state.record.candidate.payload.source_plane
    editWireNetwork(current => moveConnectedWirePoint(current, id, index, point, plane.width_pixels, plane.height_pixels, snap, presentations))
  }

  function handleAddWire(points,vertices=points.map(point=>({point})),attributes={}) {
    if (saveState.status === 'saving' || draft.wirings.length >= 2048) return false
    try { pushDraft(commitWiringPath(draft,vertices,{...withWiringMethod({},drawingWireMethod),...attributes}),{autoConnect:false}) }
    catch(error){setSaveState({status:'error',message:error.message});return false}
    setLayers((current) => ({ ...current, wirings: true }))
    return true
  }

  function editWireNetwork(edit) {
    if (saveState.status === 'saving') return
    try { pushDraft(edit(draft)) }
    catch (error) { setSaveState({status:'error',message:error.message}) }
  }

  function addEntity(kind) {
    if(drawingPending){setSaveState({status:'error',message:'Finish wiring with Done or Enter first.'});return}
    if (kind === 'symbol') {
      setTool('place-device'); setSelected(null); setPlacementLegendId(''); setView('2d')
      setLayers(current => ({...current, symbols: true}))
      return
    }
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
    if (drawingPending) {setSaveState({status:'error',message:'Finish wiring with Done or Enter before saving.'});return}
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
        ...reviewGeometryPayload(!draftOnly && reviewComplete ? { ...draft,
          ...Object.fromEntries(['walls','rooms','symbols'].map(key => [key,draft[key].map(item => item.disposition === 'unresolved' ? { ...item, disposition: 'accepted' } : item)])),
        } : draft),
        openings:draft.openings??[],
        ...wiringSavePayload(draft.wirings),
      })
      setState((current) => ({ ...current, record }))
      const savedDraft = initialDraft(record,state.legends)
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

  if (state.status === 'loading') return <div className="detection-state" role="status">Loading plan editor…</div>
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
        <span>3 · Save &amp; continue editing</span>
      </nav>
      <header className="detection-review-header">
        <div>
          <h1>Plan editor</h1>
        </div>
      </header>
      <details className="demo-detection-details"><summary>Diagnostics</summary>
      <p>{activeWallsCount} wall segments / {activeRoomsCount} rooms / analysis #{processingJobId}</p>
      <WiringRecoveryStatus report={state.record.candidate.payload.observed_routes?.recovery} presentations={presentations} />
      {truncated.length > 0 && <p>Detection limit reached: {truncated.join(', ')}.</p>}
      <p role="note">
        Automatic detection can mistake wiring, grids and dimensions for walls. All draft items are editable; saving does not certify the design.
      </p>
      {experimental && <p role="note">Experimental two-template Pull station detector; similarity is not calibrated confidence. Edit or remove incorrect devices. Other classes may be missing.</p>}
      {general && <p role="note">The shared development detector uses the trained legend catalog. Sparse or synthetic examples and conflicting labels limit results; independent accuracy remains unverified. Edit names and positions as needed.</p>}
      {(trained || linked) && <p role="note">Legacy limited-class detector. {linked ? 'Five classes with uneven same-source recall.' : 'Troffer, smoke detector and Pull station only.'} Independent-project accuracy is unverified.</p>}
      </details>
      {state.record.draft_wiring_limitations?.length > 0 && <details><summary>Wiring connectivity</summary>{state.record.draft_wiring_limitations.map(note => <p key={note}>{note}</p>)}</details>}
      {state.legends.length === 0 && <details><summary>Do I need a symbol legend?</summary><p>Not for wall review or 3D preview. Electrical-symbol approval requires an approved VED legend.</p></details>}

      <SourceViewsPanel key={state.record.candidate_run_id} record={state.record} region={analysisRegion}
        onRegionChange={setAnalysisRegion} onSelectRegion={() => { setView('2d'); setTool('region') }}
        onFreezeRegion={() => setTool('select')}
        projectId={projectId} projectFloorId={projectFloorId} floorPlanId={floorPlanId} />
      <ViewportFrame title="Plan workspace" status={saveState.message || 'Shared editable draft · save before leaving'}>
      <div className="studio-review-headerbar">
        <div className="studio-review-mode" role="group" aria-label="Preview mode">
          <Button variant={view === '2d' ? 'secondary' : 'ghost'} size="sm" disabled={drawingPending} aria-pressed={view === '2d'} aria-label="2D · Review rooms" onClick={() => {setView('2d');if(tool==='transform')setTool('select')}}><Layers3 aria-hidden="true" />Edit 2D</Button>
          <Button variant={view === '3d' ? 'secondary' : 'ghost'} size="sm" disabled={drawingPending} aria-pressed={view === '3d'} aria-label="3D · Draft preview" onClick={() => { setOpened3d(true); setView('3d'); setTool('select') }}><Box aria-hidden="true" />View 3D</Button>
        </div>
        <Button variant="ghost" size="icon" aria-label="Undo" disabled={historyIndex <= 0} onClick={handleUndo}><Undo2 aria-hidden="true" /></Button>
        <Button variant="ghost" size="icon" aria-label="Redo" disabled={historyIndex >= history.length - 1} onClick={handleRedo}><Redo2 aria-hidden="true" /></Button>
        <Button size="sm" disabled={saveState.status === 'saving'} aria-label="Save unfinished draft" onClick={() => saveReview({ draftOnly: true })}><Save aria-hidden="true" />Save draft</Button>
      </div>
      <div className="studio-review-workbench studio-device-workbench">
      <WorkspacePanel title="Plan tools" className="studio-review-tools-panel">
      <ReviewToolRail view={view} tool={tool} onToolChange={(nextTool) => {
        if(drawingPending){setSaveState({status:'error',message:'Finish wiring with Done or Enter first.'});return}
        setTool(nextTool); setEditingSession((value) => value + 1)
        if (nextTool === 'wire') setSelected(null)
      }} onAdd={addEntity}
        layers={layers} setLayers={setLayers} opacity={blueprintOpacity} onOpacityChange={setBlueprintOpacity}
        wiringControls={<>
          {tool === 'wire' && <fieldset className="studio-wire-method" disabled={drawingPending}>
            <legend>New wiring</legend>
            <label>Wiring placement<select value={drawingWireMethod} onChange={event => setDrawingWireMethod(event.target.value)}>
              <option value="concealed_in_ceiling">Ceiling</option>
              <option value="concealed_under_floor">Underground / under floor</option>
            </select></label>
            <p>Snap to a device or existing wire. Depth and height stay unset until you enter them.</p>
          </fieldset>}
          <ObservedWiringPanel wires={draft.wirings} width={plane.width_pixels} height={plane.height_pixels}
            disabled={saveState.status === 'saving'}
            view={view} visible={Boolean(layers.wirings)} onVisibilityChange={(visible) => setLayers((current) => ({ ...current, wirings: visible }))}
            onChange={wirings => editWireNetwork(current => applyWireEdits(current,wirings))} />
        </>} />
      </WorkspacePanel>
      <section className="demo-preview-workspace" aria-label="Wall-first workspace">

        <p className="demo-next-step">
          {view === '2d'
            ? tool === 'wire' ? 'Click to add points. Enter or Done finishes; Backspace removes the last point. Escape finishes without the preview.' : tool === 'draw' ? 'Click A → B → C to keep drawing walls. Escape finishes; Shift keeps it straight.' : 'Click a device or wire to edit. Save when ready.'
            : ['wire','draw'].includes(tool) ? 'Configure the work plane, then click points. Done finishes; Escape cancels the active stroke.' : 'Click a wire and drag its blue points. Devices and wiring share the same 2D/3D draft.'}
        </p>

        <div hidden={view !== '2d'}>

            {draft.walls.length === 0 && (
              <p role="status">No walls detected. Click &quot;Draw Walls&quot; above to draw walls directly over the blueprint.</p>
            )}
            <DemoInterpretationCanvas
              active={view==='2d'}
              image={state.image}
              width={plane.width_pixels}
              height={plane.height_pixels}
              draft={draft}
              selected={selected}
              onSelect={setSelected}
              layers={layers}
              tool={tool}
              editingSession={editingSession}
              {...(state.record.candidate.payload.warnings?.some(w => w.code === 'separate_source_views')
                ? { analysisRegion, onAnalysisRegionChange: setAnalysisRegion } : {})}
              onToolChange={setTool}
              onAddWall={handleAddWall}
              onUpdateWall={handleUpdateWall}
              onDeleteWall={handleDeleteWall}
              scaleMeters={state.record.routing_context?.pixels_per_meter??null}
              wallUnit={preferences.units === 'imperial' ? 'ft' : 'm'}
              onUpdateRoom={updateRoom}
              onUpdateSymbol={updateSymbol}
              placementPresentation={placementLegendId ? describeReviewSymbol({id:'placement', symbol_legend_id:Number(placementLegendId), center:{x:0,y:0}},state.record,state.legends) : null}
              onPlaceDevice={(center) => {
                if (saveState.status === 'saving' || !placementLegendId) return
                const id = nextManualId(draft.symbols, 'manual-symbol')
                pushDraft({...draft, symbols:[...draft.symbols,{id,center,disposition:'added',symbol_legend_id:Number(placementLegendId)}]})
                setSelected({kind:'symbol',id}); setTool('select'); setPlacementLegendId('')
              }}
              onDeleteSymbol={removeSymbol}
              onMoveWirePoint={moveWirePoint}
              drawingWireMethod={drawingWireMethod}
              presentations={presentations}
              blueprintOpacity={blueprintOpacity}
              onDrawingPendingChange={setDrawingPending}
              onAddWire={handleAddWire}
            />
        </div>
        {(opened3d || view === '3d') && <div hidden={view !== '3d'}>
          <Suspense fallback={<p role="status">Opening draft 3D preview…</p>}>
            <DraftRoomPreview draft={draft} layers={layers} width={plane.width_pixels} height={plane.height_pixels} projectId={projectId}
              routingContext={state.record.routing_context}
              presentations={presentations} selected={selected} onSelect={setSelected} onUpdateSymbol={updateSymbol}
              onMoveWirePoint={moveWirePoint} navigationMode={view==='3d'?tool:'select'}
              onAddWire={handleAddWire} onAddWall={handleAddWall} onToolChange={setTool} editingSession={editingSession}
              onDrawingPendingChange={setDrawingPending} drawingWireMethod={drawingWireMethod} drawingDisabled={saveState.status==='saving'} />
          </Suspense>
        </div>}
        {staleRoomsWarning && (
          <div className="demo-stale-rooms-banner" role="alert">
            <span>Wall edits invalidate automatic room boundaries. Review room corners or proceed with a walls-only layout.</span>
            <button type="button" className="btn-stale-dismiss" onClick={excludeStaleRooms}>Exclude stale room polygons</button>
          </div>
        )}
        {saveState.message && <p role={saveState.status === 'error' ? 'alert' : 'status'}>{saveState.message}</p>}
      </section>

      <WorkspacePanel title="Item inspector" className="demo-review-tools" labelledBy="demo-tools-title">
        {tool === 'place-device' && <fieldset><legend>Add device</legend>
          <DevicePicker legends={state.legends} value={placementLegendId} onChange={setPlacementLegendId}
            disabled={saveState.status==='saving'} onCancel={()=>setTool('select')} />
          <p>Click the blueprint to place one device. Escape cancels. Touching wire endpoints connect automatically.</p>
          <Button variant="outline" onClick={() => setTool('select')}>Cancel placement</Button>
        </fieldset>}
        <h2 id="demo-tools-title">Edit item</h2>

        <ObjectBrowser key={`${floorPlanId}:${processingJobId}`} draft={draft} presentations={presentations}
          selected={selected} disabled={drawingPending || saveState.status === 'saving'} onSelect={item => {
            setSelected(item)
            setLayers(current => ({ ...current, [`${item.kind}s`]: true }))
          }} />
        <details><summary>All items / rooms</summary>
        <label>Select item
          <select disabled={drawingPending || saveState.status === 'saving'} value={selected ? `${selected.kind}:${selected.id}` : ''} onChange={(event) => {
            const [kind, id] = event.target.value.split(':')
            setSelected(event.target.value ? { kind, id } : null)
            if (event.target.value) setLayers((current) => ({ ...current, [`${kind}s`]: true }))
          }}>
            <option value="">Choose an item</option>
            {orderNamed(['symbol', 'wall', 'room', 'wiring'].flatMap(kind => draft[`${kind}s`].filter(item=>item.disposition!=='rejected').map(item => ({kind,item,id:`${kind}:${item.id}`,label:kind === 'symbol' ? presentations[item.id].label : item.name || `${kind} ${item.id}`}))), choice => choice.label).map(({kind,item,id,label}) => <option key={id} value={`${kind}:${item.id}`}>{label}{item.origin === 'generated' ? ' · Automatic A* draft' : ''}</option>)}
          </select>
        </label>
        </details>
        {selectedEntity && <div className="demo-selected-editor">
          <h3>{selected.kind === 'symbol' ? presentations[selectedEntity.id].name : `${selected.kind} ${selectedEntity.id}`}</h3>
          {selected.kind === 'symbol' && <p className="studio-device-provenance">{presentations[selectedEntity.id].mapped ? 'Catalog class linked automatically or saved' : 'No unique catalog match; choose the class below'} · Class and price edits apply to {relatedSymbolIds(draft.symbols,selectedEntity.id,state.record).length} matching devices in this plan.</p>}
          {selected.kind === 'symbol' && presentations[selectedEntity.id].family!=='annotation'
            && draft.wirings.some(w => w.source_evidence_required)
            && !draft.wirings.some(w => w.disposition!=='rejected' && w.device_attachments?.some(a => a.symbol_id===selectedEntity.id))
            && <p role="note">No source-supported wire connection was resolved for this device. Edit its wiring; nearby lines are not electrical connections.</p>}
          {selected.kind === 'wall' && (
            <>
              <WallDimensionEditor key={selectedEntity.id} wall={selectedEntity} pixelsPerMeter={state.record.routing_context?.pixels_per_meter}
                onUpdate={handleUpdateWall} onError={message=>setSaveState({status:'error',message})} />
              <NumericPoint label="Start point" value={selectedEntity.start} onChange={(start) => updateSelected({ ...selectedEntity, start })} />
              <NumericPoint label="End point" value={selectedEntity.end} onChange={(end) => updateSelected({ ...selectedEntity, end })} />
              <button type="button" className="btn btn-outline-danger" onClick={() => handleDeleteWall(selectedEntity.id)}>Delete wall</button>
              {draft.symbols.some(s=>s.disposition!=='rejected' && s.mounting_wall_id===selectedEntity.id) &&
                <Button variant="outline" onClick={()=>handleDeleteWall(selectedEntity.id,true)}>Keep devices in place & delete wall</Button>}
            </>
          )}
          {selected.kind === 'wiring' && <>
            <label>Circuit identifier (connected network)<input value={selectedEntity.circuit_id ?? ''} maxLength="80"
              onChange={event => updateSelected({...selectedEntity,circuit_id:event.target.value || null})} /></label>
            <WireJunctionEditor key={selectedEntity.id} wire={selectedEntity} draft={draft}
              disabled={saveState.status === 'saving' || selectedEntity.disposition === 'rejected'} onEdit={editWireNetwork} />
            {selectedEntity.assignment_state==='unresolved' && <p role="note">Geometric A* draft only. Circuit, service level and electrical assignment are unresolved; not eligible for measured electrical quantities. Moving an endpoint device requires reviewing this alternative again.</p>}
            <label>Wiring placement<select value={selectedEntity.installation_method || 'unknown'}
              onChange={event => updateSelected(withWiringMethod(selectedEntity,event.target.value))}>
              <option value="unknown" disabled>Not specified</option>
              <option value="concealed_in_ceiling">Ceiling</option>
              <option value="concealed_under_floor">Underground / under floor</option>
            </select></label>
            <p>{selectedEntity.origin === 'generated' ? 'Automatic A* draft' : selectedEntity.path_origin === 'manual' ? 'Drawn path' : 'Drawing trace'}</p>
            {state.record.candidate.payload.observed_routes?.connections?.filter(c => c.from_ref===`segment:${selectedEntity.id}` && c.ambiguity==='ambiguous').map(c =>
              <p role="note" key={c.id}>Unresolved contact: {c.to_ref.replace('symbol:','')} · overlapping or ambiguous device port. Edit the connection rather than guessing.</p>)}
            <p>Drag a free blue endpoint onto a device or compatible path in either view. Green previews the connection; release to commit, Escape to cancel.</p>
            <WireDeviceConnections wire={selectedEntity} draft={draft} presentations={presentations}
              disabled={saveState.status === 'saving' || selectedEntity.disposition === 'rejected'}
              onConnect={(index,snap) => moveWirePoint(selectedEntity.id,index,snap.point,snap)}
              onDetach={index => updateSelected({...selectedEntity,
                auto_connect_disabled_endpoints:[...new Set([...(selectedEntity.auto_connect_disabled_endpoints || []),index])],
                device_attachments:(selectedEntity.device_attachments || []).filter(a => a.point_index !== index)})} />
            <details><summary>Advanced coordinates</summary>
              {selectedEntity.points.map((point,index) => <NumericPoint key={index} label={`Wire point ${index+1}`} value={point}
                onChange={p => moveWirePoint(selectedEntity.id,index,p)} />)}
            </details>
            <label>Wire height (m, optional)<input type="number" min="-1000" max="10000" step="0.1" value={selectedEntity.elevation_meters ?? ''}
              onChange={e => { const value = e.target.value === '' ? null : Number(e.target.value)
                if (value === null || (Number.isFinite(value) && value >= -1000 && value <= 10000)) updateSelected({ ...selectedEntity, elevation_meters: value }) }} /></label>
            <small>Wire elevation uses the project datum; device mounting height is measured above its floor. Missing heights do not block draft saves.</small>
            <Button variant="outline" onClick={() => updateSelected({ ...selectedEntity, disposition: 'rejected' })}>Remove wiring</Button>
          </>}
          {selected.kind === 'room' && <>
            <label>Room name<input value={selectedEntity.name || ''} maxLength="255" onChange={(event) => updateSelected({ ...selectedEntity, name: event.target.value || null })} /></label>
            <div className="demo-room-points">{selectedEntity.boundary.map((point, index) => <NumericPoint key={`${selectedEntity.id}-${index}`} label={`Boundary point ${index + 1}`} value={point} onChange={(nextPoint) => updateSelected({ ...selectedEntity, boundary: selectedEntity.boundary.map((item, pointIndex) => pointIndex === index ? nextPoint : item) })} />)}</div>
            <Button variant="outline" onClick={() => updateSelected({ ...selectedEntity, disposition: 'rejected' })}>Remove room</Button>
          </>}
          {selected.kind === 'symbol' && <>
            {presentations[selectedEntity.id].gangProposal?.basis==='user_requested_default' && <div>
              <p role="note" className="studio-device-provenance">The original one-gang count was defaulted, not read from the drawing. Original prediction is retained; this draft is not training truth.
                {selectedEntity.gang_count_confirmed ? ' Your class correction is recorded.' : ' Correct the VED class before final approval; unfinished saving is available.'}</p>
              {!selectedEntity.gang_count_confirmed && <Button variant="outline" disabled={!selectedEntity.symbol_legend_id}
                onClick={()=>updateDeviceType({symbol_legend_id:selectedEntity.symbol_legend_id,gang_count_confirmed:true})}>Record switch class correction</Button>}
            </div>}
            {presentations[selectedEntity.id].trainingLegend && <div className="studio-device-provenance">
              Trained legend: {presentations[selectedEntity.id].trainingLegend.name}<br />
              Drawing entry: {presentations[selectedEntity.id].trainingLegend.legend_entry} · Model class {presentations[selectedEntity.id].trainingLegend.model_class_id}
              {!presentations[selectedEntity.id].mapped && <p>No unique active catalog match for this drawing entry.</p>}
            </div>}
            <NumericPoint label="Symbol center (source pixels)" value={selectedEntity.center} onChange={(center) => updateSymbol({ ...selectedEntity, center })} />
            <label>VED legend class<select value={selectedEntity.symbol_legend_id || ''} onChange={(event) => updateDeviceType({symbol_legend_id: event.target.value ? Number(event.target.value) : null,custom_unit_price:null,
              ...(presentations[selectedEntity.id].gangProposal?.basis==='user_requested_default' ? {gang_count_confirmed:Boolean(event.target.value)} : {})})}>
              <option value="">Unmapped</option>{groupLegendChoices(state.legends, { selectedId: selectedEntity.symbol_legend_id }).map((legend) => <option key={legend.id} value={legend.id} disabled={isWiringLegend(legend)}>{legend.class_id} — {legend.displayName}{isWiringLegend(legend) ? ' — Wiring reference, not a device' : ''}</option>)}
            </select></label>
            <p className="studio-device-provenance">Use Select &amp; move devices to drag. Release on the green endpoint preview to attach; proximity alone does not connect.</p>
            <label>Mounting height above floor (m, optional)<input type="number" min="0" max="100" step="0.01"
              value={selectedEntity.mounting_height_meters ?? ''} onChange={event => {
                const value = event.target.value === '' ? null : Number(event.target.value)
                if (value === null || (Number.isFinite(value) && value >= 0 && value <= 100)) updateSymbol({...selectedEntity,mounting_height_meters:value})
              }} /></label>
            <label>Mounting wall (optional)<select value={selectedEntity.mounting_wall_id ?? ''}
              onChange={event => updateSymbol({...selectedEntity,mounting_wall_id:event.target.value || null})}>
              <option value="">Not specified</option>{orderNamed(draft.walls.filter(w => w.disposition !== 'rejected'),w => w.id)
                .map(w => <option key={w.id} value={w.id}>{w.id}</option>)}
            </select></label>
            <Button variant="outline" disabled={!draft.wirings.some(w => w.disposition!=='rejected' && (w.device_attachments || []).some(a => a.symbol_id === selectedEntity.id))}
              onClick={() => pushDraft(detachDevice(draft,selectedEntity.id))}>Detach from wiring</Button>
            <label>Custom device unit price (PHP, optional)<input type="number" min="0" max="1000000000" step="0.01"
              value={selectedEntity.custom_unit_price ?? ''} onChange={event => {
                const value = event.target.value === '' ? null : Number(event.target.value)
                if (value === null || (Number.isFinite(value) && value >= 0 && value <= 1000000000)) updateDeviceType({custom_unit_price:value})
              }} /></label>
            <p className="studio-device-provenance">Price per device, applied to matching devices. Save the draft to update the BOM. Does not change Admin prices.</p>
            <Button variant="outline" className="studio-remove-device" disabled={selectedEntity.disposition === 'rejected'} onClick={() => removeSymbol(selectedEntity.id)}><Trash2 aria-hidden="true" />Remove device</Button>
          </>}
        </div>}
        {!selectedEntity && <p className="studio-inspector-empty">Select a named device in the canvas or list to move, classify or remove it. Changes stay in the shared draft until saved.</p>}
      </WorkspacePanel>

      </div>
      </ViewportFrame>
      <details className="demo-approval-panel"><summary>Measured layout &amp; estimates (optional)</summary>
      <section aria-labelledby="demo-approval-title">
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
      </details>
      <section className="studio-review-estimation" aria-label="Plan estimation">
        <BOMPanel projectId={projectId} floorPlanId={floorPlanId} processingJobId={state.record.processing_job_id}
          designer={session?.user?.role === 'DESIGNER'}
          unsaved={Boolean(draft && state.record && JSON.stringify(draft) !== JSON.stringify(initialDraft(state.record,state.legends)))}
          refreshKey={state.record.review?.revision_number || 0} />
      </section>
    </article>
  )
}
