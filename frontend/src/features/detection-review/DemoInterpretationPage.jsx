import {WireHeightEditor} from './WireHeightEditor.jsx'
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import {RoomMeasurementSummary} from './RoomMeasurementSummary.jsx'
import {listFloorPlans} from '../../api/floorPlans.js'
import { useUserPreferences } from '../settings/useUserPreferences.js'
import { ViewportFrame } from '../../components/ViewportFrame.jsx'
import { WorkspacePanel } from '../../components/WorkspacePanel.jsx'

import {
  DemoInterpretationApiError,
  fetchDemoInterpretation,
  saveDemoReview,
} from '../../api/demoInterpretation.js'
import { LayoutApiError } from '../../api/layouts.js'
import {usePlanMeasurements} from './usePlanMeasurements.js'
import { fetchReviewImage } from '../../api/reviewImages.js'
import { fetchSymbolLegends, isWiringLegend } from '../../api/symbolLegends.js'
import { groupLegendChoices } from '../../api/legendChoices.js'
import {
  getProjectHref,
} from '../../routes/projectRoutes.js'
import { DemoInterpretationCanvas } from './DemoInterpretationCanvas.jsx'
import { ScalePanel } from './ScalePanel.jsx'
import {WiringCheckPanel} from './WiringCheckPanel.jsx'
import { ObservedWiringPanel } from './ObservedWiringPanel.jsx'
import { WireDeviceConnections } from './WireDeviceConnections.jsx'
import { BOMPanel } from '../estimation/BOMPanel.jsx'
import {ManualBOMSettings} from '../estimation/ManualBOMSettings.jsx'
import {IndividualPriceEditor} from '../estimation/IndividualPriceEditor.jsx'
import {WorkspaceProductEditor} from './WorkspaceProductEditor.jsx'
import {WorkspaceGuide} from './WorkspaceGuide.jsx'
import { initialWiringDraft, wiringSavePayload } from './observedWiringDraft.js'
import { withWiringMethod } from './wireDrawing.js'
import { predominantWireMethod } from './wireAssignments.js'
import { connectTouchingWireEndpoints, detachDevice, moveConnectedDevice, moveConnectedWirePoint } from './deviceConnections.js'
import './detectionReview.css'
import { Button } from '../../components/ui/button.jsx'
import { ArrowLeft, Box, Layers3, Undo2, Redo2, Save, Trash2, ChevronDown, List } from 'lucide-react'
import { PlanInformation } from './PlanInformation.jsx'
import { ReviewToolRail } from './ReviewToolRail.jsx'
import { orderNamed } from '../../utils/listOrder.js'
import { autoLinkSymbols, clampDevicePoint, describeReviewSymbol, relatedSymbolIds, updateRelatedSymbols, reviewGeometryPayload } from './devicePresentation.js'
import { addConnectedWall, moveConnectedWall, deleteConnectedWall } from './wallDrawing.js'
import { WallDimensionEditor } from './WallDimensionEditor.jsx'
import { pastedDevice, useDeviceClipboard } from './useDeviceClipboard.js'
import { WireJunctionEditor } from './WireJunctionEditor.jsx'
import {saveMaterialSelection} from '../../api/materialSelection.js'
import { WiringRecoveryStatus } from './WiringRecoveryStatus.jsx'
import { updateWireNetwork, applyWireEdits } from './wireJunctions.js'
import { DevicePicker } from './DevicePicker.jsx'
import { commitWiringPath } from './connectedWiring.js'
import { ObjectBrowser } from './ObjectBrowser.jsx'
import { DraftSubmission } from './DraftSubmission.jsx'
import { NotificationCenter } from '../../components/NotificationCenter.jsx'

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
  // Resolve plan defaults in scene/takeoff adapters, not as item overrides.
  // Otherwise switching setup leaves synthetic old heights frozen in the draft.
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
        ...Object.fromEntries(['mounting_reference','mounting_height_source','terminal_offset_meters'].filter(k=>symbol[k]!=null).map(k=>[k,symbol[k]])),
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


export function DemoInterpretationPage({ projectId, projectFloorId, floorPlanId, processingJobId, session,measurementAction,measurementTarget,measurementTargets=[] }) {
  const canEdit = session?.user?.role === 'DESIGNER'
  const [state, setState] = useState({ status: 'loading', record: null, image: null, legends: [], error: null })
  const [draft, setDraft] = useState(null)
  const [studioBOM,setStudioBOM]=useState(null)
  const [studioShowcase,setStudioShowcase]=useState(false)
  const [selected, setSelected] = useState(measurementTarget && ['wire-height','device-height','wiring'].includes(measurementAction) ? {kind:measurementAction==='device-height'?'symbol':'wiring',id:measurementTarget}:null)
  const [notes, setNotes] = useState('')
  const routeProduct=measurementAction?.startsWith('product')?measurementTarget:null
  const [productSelection,setProductSelection]=useState({request:routeProduct,id:routeProduct})
  const productId=productSelection.request===routeProduct?productSelection.id:routeProduct
  const routeMaterialField={'material-wire':'wire-product','material-wire-length':'wire-length','material-conduit-length':'conduit-length','material-conductor-count':'conductor-count'}[measurementAction]
  const [materialFocus,setMaterialFocus]=useState({request:measurementAction,field:routeMaterialField})
  const materialField=materialFocus.request===measurementAction?materialFocus.field:routeMaterialField
  const productItem=draft?.symbols.find(s=>s.id===productId) || draft?.wirings.find(w=>w.id===productId)
  const productKind=draft?.symbols.some(s=>s.id===productId)?'symbol':'wiring'
  const effectiveSelection=productItem?{kind:productKind,id:productId}:selected
  useEffect(()=>{
    if(!productItem)return
    const frame=requestAnimationFrame(()=>document.querySelector('.studio-review-page .studio-viewport-frame')?.scrollIntoView({block:'start',behavior:'instant'}))
    return()=>cancelAnimationFrame(frame)
  },[productItem,measurementAction])
  function closeProduct(){if(productItem)setSelected({kind:productKind,id:productItem.id});setProductSelection({request:routeProduct,id:null})}
  function closeMaterialDefaults(){setMaterialFocus({request:measurementAction,field:null})}
  function openProduct(item){
    if(drawingPending)return
    setSelected(item);setInspectorOpen(false);closeMaterialDefaults()
    setProductSelection({request:routeProduct,id:item.id})
  }
  function openMaterialDefaults(field='wire-product'){
    if(drawingPending)return
    closeProduct();setInspectorOpen(false);setMaterialFocus({request:measurementAction,field})
    document.querySelector('.studio-review-page .studio-viewport-frame')?.scrollIntoView({block:'start'})
  }
  async function savePlanMaterials(settings){
    if(!studioBOM?.planning)return
    setSaveState({status:'pricing',message:'Applying material settings…'})
    try{await saveMaterialSelection(projectId,{floorPlanId,requestId:crypto.randomUUID(),expectedVersion:studioBOM.planning.material_selection_revision || 0,settings});setScaleRevision(n=>n+1);closeMaterialDefaults();setSaveState({status:'idle',message:'Material settings saved. BOM updated.'})}
    catch(error){setSaveState({status:'error',message:error.message})}
  }
  const [wallThickness, setWallThickness] = useState('')
  const [wallHeight, setWallHeight] = useState('')
  const [reviewComplete, setReviewComplete] = useState(false)
  const [approveLayout, setApproveLayout] = useState(false)
  const [saveState, setSaveState] = useState({ status: 'idle', message: null })
  const [rulerStatus,setRulerStatus] = useState({status:'idle',message:null})
  const [scaleRevision,setScaleRevision] = useState(0)
  const measurements=usePlanMeasurements(projectId,floorPlanId,processingJobId)
  const rulerRequest = useRef(null)
  const [inspectorOpen, setInspectorOpen] = useState(Boolean(measurementTarget && ['wire-height','device-height','wiring'].includes(measurementAction)))
  const [view, setView] = useState('2d')
  const [opened3d, setOpened3d] = useState(false)
  // Default to wall-focused view with rooms hidden
  const { preferences } = useUserPreferences()
  const [layers, setLayers] = useState(() => ({ walls: preferences.walls, rooms: false, symbols: preferences.symbols, names: false, dimensions: true, wirings: preferences.wiring, source: preferences.blueprint }))
  const [tool, setTool] = useState('select')
  const [placementLegendId, setPlacementLegendId] = useState('')
  const [chosenWireMethod, setDrawingWireMethod] = useState(null)
  const drawingWireMethod = chosenWireMethod ?? predominantWireMethod(draft?.wirings)
  const [drawingPending,setDrawingPending] = useState(false)
  const [editingSession, setEditingSession] = useState(0)
  const [analysisRegion, setAnalysisRegion] = useState(null)
  const navigationPanel=['view','scale','heights'].includes(measurementAction) ? measurementAction:null
  const [measurementPanel,setMeasurementPanel]=useState({action:measurementAction,panel:navigationPanel})
  const scalePanel=measurementPanel && typeof measurementPanel==='object' ? measurementPanel.action===measurementAction ? measurementPanel.panel:navigationPanel : measurementPanel ?? navigationPanel
  const setScalePanel=panel=>setMeasurementPanel({action:measurementAction,panel})
  const measurementFocus=measurementPanel?.focus || {kind:measurementAction,target:measurementTarget}
  const [wiringCheck,setWiringCheck]=useState({action:measurementAction,open:measurementAction==='wiring' && !measurementTarget})
  const checkWiring=typeof wiringCheck==='boolean' ? wiringCheck : wiringCheck.action===measurementAction ? wiringCheck.open:measurementAction==='wiring' && !measurementTarget
  const setCheckWiring=open=>setWiringCheck({action:measurementAction,open})
  const [blueprintOpacity, setBlueprintOpacity] = useState(1.0)
  const [history, setHistory] = useState([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const pastePointer = useRef(null)
  const staleRoomsWarning = Boolean(draft && history[0]
    && draft.rooms.some(room => room.id.startsWith('room-') && room.disposition !== 'rejected')
    && JSON.stringify(draft.walls) !== JSON.stringify(history[0].walls))

  useEffect(()=>()=>rulerRequest.current?.abort(),[floorPlanId,processingJobId])

  async function applyRuler(measuredRuler) {
    if(session?.user?.role!=='DESIGNER' || rulerStatus.status==='saving')return
    const record=state.record
    const controller=new AbortController()
    rulerRequest.current=controller
    setRulerStatus({status:'saving',message:null})
    let saved=false
    try {
      const result=await measurements.save({measurement_method:'reference',reference:measuredRuler})
      if(!result)throw new Error('Reference could not be saved')
      saved=true
      const updated=await fetchDemoInterpretation(floorPlanId,{processingJobId,signal:controller.signal})
      if(controller.signal.aborted)return
      // Refresh measurement context only: never replace unsaved geometry/history.
      setState(current=>current.record?.processing_job_id===record.processing_job_id
        ? {...current,record:{...current.record,routing_context:updated.routing_context}}:current)
      setScaleRevision(value=>value+1)
      setLayers(current=>({...current,dimensions:true}))
      setRulerStatus({status:'saved',message:'Ruler scale saved. BOM is recalculating.'})
    } catch(error) {
      if(controller.signal.aborted)return
      if(error.status===401)window.location.replace('#/signin?reason=session-expired')
      setRulerStatus({status:'error',message:saved
        ? 'Scale saved, but the view could not refresh. Reload to see updated measurements.'
        : 'Ruler scale could not be saved. Please retry.'})
    }
  }

  async function saveSheet(displayOnly=false,automatic=false) {
    const job=state.record?.processing_job_id
    const saved=await measurements.save({}, {displayOnly,automatic})
    if(!saved)return
    // Display framing never invalidates takeoff or applies pending source edits.
    if(displayOnly)return
    // The write response is the authoritative context; another fetch must not
    // leave the panel and 3D on different revisions after a successful save.
    setState(current=>current.record?.processing_job_id===job
      ? {...current,record:{...current.record,routing_context:{...current.record.routing_context,
        ...saved.effective_measurement,floor_elevation_meters:saved.floor_elevation_meters}}}:current)
    setScaleRevision(value=>value+1)
  }
  const sheetModel={...measurements,onSave:()=>saveSheet(),onSaveDisplay:()=>saveSheet(true),onAutomatic:()=>saveSheet(false,true)}

  function openRuler() {
    if(drawingPending){setSaveState({status:'error',message:'Finish or cancel the wiring path before using the ruler.'});return}
    setCheckWiring(false);setScalePanel(null);setView('2d');setTool('ruler')
    document.querySelector('.studio-review-page .studio-viewport-frame')?.scrollIntoView({block:'start',behavior:'smooth'})
  }
  function openScale(section='scale',target,targets=[]) {
    if(drawingPending){setSaveState({status:'error',message:'Finish the current wire with Done or Enter before opening another setting.'});return}
    if(['wire-height','device-height'].includes(section) && target){
      setMeasurementPanel({action:measurementAction,panel:null,focus:{kind:section,target,targets}})
      selectItem({kind:section==='device-height'?'symbol':'wiring',id:target});setView('2d');setTool('select');setCheckWiring(false)
      requestAnimationFrame(()=>{document.querySelector('.studio-review-page .studio-viewport-frame')?.scrollIntoView({block:'start'});const input=document.querySelector(section==='wire-height'?'[data-wire-height]':'[data-device-height]');input?.focus({preventScroll:true});input?.scrollIntoView({block:'nearest'})})
      return
    }
    if(section==='wiring' && target){
      const wire=draft?.wirings.find(w=>w.id===target)
      const knownPlacement=wire?.installation_method && wire.installation_method!=='unknown'
      const occupied=new Set([...(wire?.device_attachments || []).filter(a=>draft.symbols.some(s=>s.id===a.symbol_id && s.disposition!=='rejected')),...(wire?.junction_attachments || [])].map(a=>a.point_index))
      const endpoint=wire ? [0,wire.points.length-1].find(index=>!occupied.has(index)):null
      setMeasurementPanel({action:measurementAction,panel:null,focus:{kind:'wiring',target}})
      setCheckWiring(false);setView('2d');setTool('select');selectItem({kind:'wiring',id:target})
      requestAnimationFrame(()=>{
        document.querySelector('.studio-review-page .studio-viewport-frame')?.scrollIntoView({block:'start'})
        const field=document.querySelector(!knownPlacement?'[data-wire-placement]':endpoint!=null?`[data-wire-connection="${endpoint}"]`:'[data-connection-defaults]')
        field?.focus({preventScroll:true});field?.scrollIntoView({block:'nearest'})
      })
      return
    }
    if(section==='wiring'){setScalePanel(null);setView('2d');setTool('select');setCheckWiring(true);return}
    setCheckWiring(false);setTool('select');setScalePanel(section)
    document.querySelector('.studio-review-page .studio-viewport-frame')?.scrollIntoView({block:'start',behavior:'smooth'})
  }
  function selectPlanArea() {
    if(drawingPending)return
    setScalePanel(null);setView('2d');setTool('region')
  }
  async function useConnectionDefaults(){
    if(!studioBOM?.planning || saveState.status==='assuming' || !canEdit)return
    setSaveState({status:'assuming',message:'Applying connection defaults…'})
    try{
      await saveMaterialSelection(projectId,{floorPlanId,expectedVersion:studioBOM.planning.material_selection_revision || 0,
        requestId:crypto.randomUUID(),settings:{...studioBOM.planning.material_selection,assumeConnections:true}})
      setScaleRevision(n=>n+1)
      setSaveState({status:'idle',message:'Connection defaults applied. BOM updated.'})
    }catch(error){setSaveState({status:'error',message:error.message})}
  }

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    let objectUrl = null
    pastePointer.current=null
    Promise.all([
      fetchDemoInterpretation(floorPlanId, { signal: controller.signal, processingJobId }),
      fetchReviewImage(floorPlanId, processingJobId, { signal: controller.signal }),
      fetchSymbolLegends({ signal: controller.signal }),
      listFloorPlans(projectId,{projectFloorId,signal:controller.signal}).catch(()=>[]),
    ]).then(async ([record, blob, legends,plans]) => {
      if (record.processing_job_id !== processingJobId) throw new DemoInterpretationApiError()
      objectUrl = URL.createObjectURL(blob)
      const image = await decodeImage(objectUrl)
      const plane = record.candidate.payload.source_plane
      if (image.naturalWidth !== plane.width_pixels || image.naturalHeight !== plane.height_pixels) {
        throw new DemoInterpretationApiError('The review image dimensions do not match the immutable candidate source plane.')
      }
      if (!active) return
      const initial = initialDraft(record,legends)
      setState({ status: 'ready', record, image, legends, error: null,planName:plans.find(plan=>plan.id===floorPlanId)?.display_name || 'Pending' })
      setRulerStatus({status:'idle',message:null})
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
  }, [floorPlanId, processingJobId,projectId,projectFloorId])

  // Keyboard undo/redo
  useEffect(() => {
    function handleKeyDown(e) {
      if(studioShowcase && view==='3d')return
      if(productItem || materialField){
        if(e.key==='Escape'){
          e.preventDefault()
          if(productItem)setSelected({kind:productKind,id:productItem.id})
          setProductSelection({request:routeProduct,id:null});setMaterialFocus({request:measurementAction,field:null})
        }
        return
      }
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
  }, [historyIndex, history, saveState.status,studioShowcase,view,productItem,materialField,productKind,routeProduct,measurementAction])

  useDeviceClipboard({
    sourceKey: `${floorPlanId}:${processingJobId}`,
    draft, selected, plane: state.record?.candidate.payload.source_plane,
    disabled: state.status !== 'ready' || saveState.status === 'saving' || drawingPending || view !== '2d' || Boolean(productItem || materialField),
    onPaste(snapshot) {
      const symbol = pastedDevice(snapshot, draft, state.record.candidate.payload.source_plane,
        nextManualId(history.flatMap(entry=>entry.symbols), 'manual-symbol'),pastePointer.current)
      if (!symbol) {
        setSaveState({status:'error',message:'No free position for a copy. Move the pointer to a clear part of the plan and try again.'})
        return
      }
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
  const focusWireHeight=measurementFocus.kind==='wire-height' && selectedEntity?.id===measurementFocus.target
  const focusDeviceHeight=measurementFocus.kind==='device-height' && selectedEntity?.id===measurementFocus.target
  const focusWiring=measurementFocus.kind==='wiring' && selected?.kind==='wiring' && selectedEntity?.id===measurementFocus.target
  const occupiedWireEnds=new Set([...(selectedEntity?.device_attachments || []).filter(a=>draft?.symbols.some(s=>s.id===a.symbol_id && s.disposition!=='rejected')),...(selectedEntity?.junction_attachments || [])].map(a=>a.point_index))
  const repairEndpoint=selected?.kind==='wiring' && selectedEntity ? [0,selectedEntity.points.length-1].find(index=>!occupiedWireEnds.has(index)):null
  const repairPlacement=focusWiring && (!selectedEntity.installation_method || selectedEntity.installation_method==='unknown')
  const presentations = useMemo(() => draft && state.record
    ? Object.fromEntries(draft.symbols.map((symbol) => [symbol.id, describeReviewSymbol(symbol, state.record, state.legends)])) : {},
  [draft, state.record, state.legends])
  const bomPreview = useMemo(() => draft && state.record ? {
    candidate_run_id:state.record.candidate_run_id,expected_revision_number:state.record.review?.revision_number ?? null,
    review_complete:false,approved_for_layout:false,wall_thickness_meters:null,wall_height_meters:null,
    evidence_notes:'Unsaved canvas preview. No approval or review is written.',
    ...reviewGeometryPayload(draft),...wiringSavePayload(draft.wirings),
  } : null,[draft,state.record])
  const savedBaseline = useMemo(() => state.record ? JSON.stringify(initialDraft(state.record,state.legends)) : '',[state.record,state.legends])
  const unsaved = useMemo(() => Boolean(draft && JSON.stringify(draft) !== savedBaseline),[draft,savedBaseline])

  function selectItem(item) {
    closeProduct();closeMaterialDefaults()
    setSelected(item)
    if (item) setInspectorOpen(view!=='3d')
  }

  function pushDraft(nextDraft, { autoConnect = true } = {}) {
    if (!canEdit) return
    if(studioShowcase && view==='3d')return
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
    catch(error){setSelected({kind:'wall',id:wallId});setInspectorOpen(true);setSaveState({status:'error',message:error.message});return}
    if (detachMounted) setSaveState({status:'idle',message:'Devices kept in place. Select a device to choose its new mounting wall.'})
    if (selected?.id === wallId) setSelected(null)
  }

  function excludeStaleRooms() {
    const nextRooms = draft.rooms.map((r) => r.id.startsWith('room-') ? { ...r, disposition: 'rejected' } : r)
    pushDraft({ ...draft, rooms: nextRooms })
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
      setInspectorOpen(true)
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
    setInspectorOpen(true)
    setLayers((current) => ({ ...current, [`${kind}s`]: true }))
    setView('2d')
  }

  async function saveReview({ draftOnly = false } = {}) {
    if(session?.user?.role!=='DESIGNER')return null
    if(studioShowcase && view==='3d')return
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
      return record
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
      <h1 className="sr-only">Plan editor</h1>
      <PlanInformation title={`${state.planName || 'Pending'} · Plan ${floorPlanId}`}>
      <details><summary>Diagnostics</summary>
        <p>{activeWallsCount} walls · {activeRoomsCount} room proposals · analysis #{processingJobId}</p>
        <WiringRecoveryStatus report={state.record.candidate.payload.observed_routes?.recovery} presentations={presentations} />
        {truncated.length > 0 && <p>Detection limit reached: {truncated.join(', ')}.</p>}
      </details>
      <details className="demo-detection-details"><summary>Detection details and limitations</summary>
      <p role="note">
        Automatic detection can mistake wiring, grids and dimensions for walls. All draft items are editable; saving does not certify the design.
      </p>
      {experimental && <p role="note">Experimental two-template Pull station detector; similarity is not calibrated confidence. Edit or remove incorrect devices. Other classes may be missing.</p>}
      {general && <p role="note">The shared development detector uses the trained legend catalog. Sparse or synthetic examples and conflicting labels limit results; independent accuracy remains unverified. Edit names and positions as needed.</p>}
      {(trained || linked) && <p role="note">Legacy limited-class detector. {linked ? 'Five classes with uneven same-source recall.' : 'Troffer, smoke detector and Pull station only.'} Independent-project accuracy is unverified.</p>}
      </details>
      {state.record.draft_wiring_limitations?.length > 0 && <details><summary>Wiring connectivity</summary>{state.record.draft_wiring_limitations.map(note => <p key={note}>{note}</p>)}</details>}
      {state.legends.length === 0 && <details><summary>Do I need a symbol legend?</summary><p>Not for wall review or 3D preview. Electrical-symbol approval requires an approved VED legend.</p></details>}

      </PlanInformation>
      <ViewportFrame title="Plan workspace" status={saveState.message || 'Shared editable draft · save before leaving'}>
      <div className="studio-review-headerbar">
        <a href={getProjectHref(projectId)} className="studio-plan-back" title="Back to project" aria-label="Back to project"><ArrowLeft size={18} /></a>
        {session?.user?.role==='DESIGNER' && <NotificationCenter/>}
        <details className="studio-plan-menu"><summary>{state.planName || 'Pending'}<ChevronDown size={14} aria-hidden="true" /></summary><div><small>Plan {floorPlanId}</small><a href={getProjectHref(projectId)}>Project &amp; floors</a><a href="#/app/settings">Editor settings</a><button type="button" className="btn btn-outline-dark" onClick={event=>{event.currentTarget.closest('details').open=false;openMaterialDefaults()}}>Material defaults</button><a href="#plan-bom" onClick={event => { event.preventDefault(); document.getElementById('plan-bom')?.scrollIntoView({behavior:'smooth'}) }}><List size={14} aria-hidden="true" />Bill of materials</a></div></details>
        <div className="studio-review-mode" role="group" aria-label="Preview mode">
          <Button variant={view === '2d' ? 'secondary' : 'ghost'} size="sm" disabled={drawingPending} aria-pressed={view === '2d'} aria-label="2D · Review rooms" onClick={() => {setView('2d');if(tool==='transform')setTool('select')}}><Layers3 aria-hidden="true" />{canEdit ? 'Edit 2D' : 'View 2D'}</Button>
          <Button variant={view === '3d' ? 'secondary' : 'ghost'} size="sm" disabled={drawingPending} aria-pressed={view === '3d'} aria-label="3D · Draft preview" onClick={() => { setOpened3d(true); setView('3d'); setTool('select') }}><Box aria-hidden="true" />View 3D</Button>
        </div>
        <Button variant="ghost" size="icon" aria-label="Undo" disabled={historyIndex <= 0 || studioShowcase && view==='3d'} onClick={handleUndo}><Undo2 aria-hidden="true" /></Button>
        <Button variant="ghost" size="icon" aria-label="Redo" disabled={historyIndex >= history.length - 1 || studioShowcase && view==='3d'} onClick={handleRedo}><Redo2 aria-hidden="true" /></Button>
        {session?.user?.role==='DESIGNER' && <Button size="sm" disabled={saveState.status === 'saving' || studioShowcase && view==='3d'} aria-label="Save unfinished draft" title={unsaved ? 'Unsaved canvas changes' : 'No unsaved changes'} onClick={() => saveReview({ draftOnly: true })}><Save aria-hidden="true" />{unsaved ? 'Save changes *' : 'Save draft'}</Button>}
      </div>
      <div className="studio-review-workbench studio-device-workbench">
      <WorkspacePanel title="Plan tools" className="studio-review-tools-panel" defaultOpen>
      <div inert={studioShowcase && view==='3d' ? true : undefined} hidden={studioShowcase && view==='3d'}><ReviewToolRail readOnly={!canEdit} view={view} tool={tool} onToolChange={(nextTool) => {
        if(drawingPending){setSaveState({status:'error',message:'Finish wiring with Done or Enter first.'});return}
        setTool(nextTool); setEditingSession((value) => value + 1)
        if (nextTool === 'wire') setSelected(null)
      }} onAdd={addEntity}
        layers={layers} setLayers={setLayers} opacity={blueprintOpacity} onOpacityChange={setBlueprintOpacity} onDisplayLayout={()=>openScale('layout')}
        rooms={draft.rooms} selectedRoomId={layers.rooms && selected?.kind === 'room' ? selected.id : ''}
        onRoomSelect={id => { selectItem(id ? {kind:'room',id} : null); setLayers(current => ({...current,rooms:Boolean(id)})); setTool('select') }}
        wiringControls={<>
          {tool === 'wire' && <fieldset className="studio-wire-method" disabled={drawingPending}>
            <legend>New wiring</legend>
            <label>Wiring placement<select value={drawingWireMethod} onChange={event => setDrawingWireMethod(event.target.value)}>
              <option value="unknown">Not specified</option>
              <option value="concealed_in_ceiling">Ceiling</option>
              <option value="concealed_under_floor">Under floor</option>
            </select></label>
            <p>Placement follows the drawing or the path you connect to.</p>
          </fieldset>}
          <ObservedWiringPanel wires={draft.wirings} width={plane.width_pixels} height={plane.height_pixels}
            onCheck={()=>{setScalePanel(null);setCheckWiring(true);setView('2d');setTool('select')}}
            disabled={!canEdit || saveState.status === 'saving'}
            view={view} visible={Boolean(layers.wirings)} onVisibilityChange={(visible) => setLayers((current) => ({ ...current, wirings: visible }))}
            onChange={wirings => editWireNetwork(current => applyWireEdits(current,wirings))} />
        </>} /></div>
      </WorkspacePanel>
      <section className="demo-preview-workspace" aria-label="Wall-first workspace">

        {['wire','draw','place-device'].includes(tool) && <p className="demo-next-step">
          {view === '2d'
            ? tool === 'wire' ? 'Click to add points. Enter or Done finishes; Backspace removes the last point. Escape finishes without the preview.' : tool === 'draw' ? 'Click A → B → C to keep drawing walls. Escape finishes; Shift keeps it straight.' : 'Click a device or wire to edit. Save when ready.'
            : ['wire','draw'].includes(tool) ? 'Configure the work plane, then click points. Done finishes; Escape cancels the active stroke.' : 'Click a wire and drag its blue points. Devices and wiring share the same 2D/3D draft.'}
        </p>}

        <div hidden={view !== '2d'}>

            <DemoInterpretationCanvas
              active={view==='2d'}
              image={state.image}
              width={plane.width_pixels}
              height={plane.height_pixels}
              draft={draft}
              selected={focusWiring && !repairPlacement ? {...effectiveSelection,repairPointIndex:repairEndpoint}:effectiveSelection}
              onSelect={selectItem}
              layers={layers}
              tool={tool}
              editingSession={editingSession}
              analysisRegion={analysisRegion}
              onAnalysisRegionChange={region=>{
                setAnalysisRegion(region)
                if(region && tool==='region'){setTool('select');setScalePanel('view')}
              }}
              onToolChange={setTool}
              onAddWall={canEdit ? handleAddWall : undefined}
              onUpdateWall={canEdit ? handleUpdateWall : undefined}
              onDeleteWall={canEdit ? handleDeleteWall : undefined}
              scaleMeters={state.record.routing_context?.pixels_per_meter??null}
              sheetModel={sheetModel}
              sheetContext={state.record.routing_context}
              onOpenScale={openScale}
              checkWiring={checkWiring}
              sourceSegments={state.record.candidate.payload.observed_routes?.segments || []}
              scalePanelOpen={Boolean(scalePanel)}
              savedRuler={state.record.routing_context?.measured_ruler}
              rulerStatus={rulerStatus}
              onApplyRuler={applyRuler}
              canSaveRuler={session?.user?.role==='DESIGNER' && saveState.status!=='saving'}
              wallUnit={preferences.units === 'imperial' ? 'ft' : 'm'}
              onUpdateRoom={canEdit ? updateRoom : undefined}
              onUpdateSymbol={canEdit ? updateSymbol : undefined}
              placementPresentation={placementLegendId ? describeReviewSymbol({id:'placement', symbol_legend_id:Number(placementLegendId), center:{x:0,y:0}},state.record,state.legends) : null}
              onPlaceDevice={(center) => {
                if (saveState.status === 'saving' || !placementLegendId) return
                const id = nextManualId(draft.symbols, 'manual-symbol')
                pushDraft({...draft, symbols:[...draft.symbols,{id,center,disposition:'added',symbol_legend_id:Number(placementLegendId)}]})
                selectItem({kind:'symbol',id}); setTool('select'); setPlacementLegendId('')
              }}
              onDeleteSymbol={canEdit ? removeSymbol : undefined}
              onMoveWirePoint={canEdit ? moveWirePoint : undefined}
              drawingWireMethod={drawingWireMethod}
              presentations={presentations}
              blueprintOpacity={blueprintOpacity}
              onDrawingPendingChange={setDrawingPending}
              onPointerChange={point=>{pastePointer.current=point}}
              onAddWire={canEdit ? handleAddWire : undefined}
            />
        </div>
        {(opened3d || view === '3d') && <div hidden={view !== '3d'}>
          <Suspense fallback={<p role="status">Opening draft 3D preview…</p>}>
            <DraftRoomPreview draft={draft} layers={layers} width={plane.width_pixels} height={plane.height_pixels} projectId={projectId}
              bom={studioBOM}
              onEditProduct={canEdit?openProduct:undefined} productEditorOpen={Boolean(productItem || materialField || inspectorOpen)} onInspectItem={item=>{setSelected(item);setInspectorOpen(true)}}
              productEditTarget={productItem?{kind:productKind,id:productItem.id}:null}
              onShowcaseChange={setStudioShowcase}
              setupRevision={scaleRevision}
              onOpenMeasurements={()=>openScale()}
              routingContext={state.record.routing_context}
              presentations={presentations} selected={effectiveSelection} onSelect={selectItem} onUpdateSymbol={canEdit ? updateSymbol : undefined}
              visibleRoomId={layers.rooms && selected?.kind === 'room' ? selected.id : null}
              onMoveWirePoint={canEdit ? moveWirePoint : undefined} navigationMode={view==='3d'?tool:'select'}
              onAddWire={canEdit ? handleAddWire : undefined} onAddWall={canEdit ? handleAddWall : undefined} onToolChange={setTool} editingSession={editingSession}
              onDrawingPendingChange={setDrawingPending} drawingWireMethod={drawingWireMethod} drawingDisabled={!canEdit || saveState.status==='saving'} />
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

      {!(studioShowcase && view==='3d') && !productItem && !materialField && <WorkspacePanel title="Item inspector" className="demo-review-tools" labelledBy="demo-tools-title" open={inspectorOpen} onOpenChange={setInspectorOpen}>
        {tool === 'place-device' && <fieldset><legend>Add device</legend>
          <DevicePicker legends={state.legends.filter(legend=>!studioBOM?.planning?.allowed_symbol_legend_ids || studioBOM.planning.allowed_symbol_legend_ids.includes(legend.id))} value={placementLegendId} onChange={setPlacementLegendId}
            disabled={saveState.status==='saving'} onCancel={()=>setTool('select')} />
          <p>Click the blueprint to place one device. Escape cancels. Touching wire endpoints connect automatically.</p>
          <Button variant="outline" onClick={() => setTool('select')}>Cancel placement</Button>
        </fieldset>}
        <h2 id="demo-tools-title">{canEdit ? 'Edit item' : 'Item details'}</h2><WorkspaceGuide section={selected?.kind==='symbol'?'device':selected?.kind==='wiring'?'wiring':'architecture'}/>
        {selected?.kind!=='room' && <ObjectBrowser key={`${floorPlanId}:${processingJobId}`} draft={draft} presentations={presentations}
          selected={selected} disabled={drawingPending || saveState.status === 'saving'} onSelect={item => {
            setSelected(item)
            setLayers(current => ({ ...current, [`${item.kind}s`]: true }))
          }} />}
        <details><summary>All items / rooms</summary>
        <label>Select item
          <select disabled={drawingPending || saveState.status === 'saving'} value={selected ? `${selected.kind}:${selected.id}` : ''} onChange={(event) => {
            const [kind, id] = event.target.value.split(':')
            setSelected(event.target.value ? { kind, id } : null)
            if (event.target.value) setLayers((current) => ({ ...current, [`${kind}s`]: true }))
          }}>
            <option value="">Choose an item</option>
            {orderNamed(['symbol', 'wall', 'room', 'wiring'].flatMap(kind => draft[`${kind}s`].filter(item=>item.disposition!=='rejected').map(item => ({kind,item,id:`${kind}:${item.id}`,label:kind === 'symbol' ? presentations[item.id].label : item.name || `${kind} ${item.id}`}))), choice => choice.label).map(({kind,item,id,label}) => <option key={id} value={`${kind}:${item.id}`}>{label}{kind === 'symbol' ? ` · ${item.id}` : ''}{item.origin === 'generated' ? ' · Automatic A* draft' : ''}</option>)}
          </select>
        </label>
        </details>
        {selectedEntity && <fieldset disabled={!canEdit} className="demo-selected-editor" style={{border:0,padding:0,minWidth:0}}>
          <h3>{selected.kind === 'symbol' ? presentations[selectedEntity.id].name : selected.kind==='room'?selectedEntity.name || 'Room':`${selected.kind} ${selectedEntity.id}`}</h3>
          {selected.kind === 'symbol' && <p className="studio-device-provenance">{presentations[selectedEntity.id].mapped ? 'Catalog class linked' : 'Choose the device symbol below'}. Symbol changes apply to {relatedSymbolIds(draft.symbols,selectedEntity.id,state.record).length} matching devices. Product changes affect only the selected device.</p>}
          {['symbol','wiring'].includes(selected.kind) && canEdit && <Button variant="outline" onClick={()=>openProduct(selected)}>Change {selected.kind==='symbol'?'brand / product':'wiring product'}</Button>}
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
            {focusWiring && <div className="wiring-fix-guide" role="status">
              <strong>{repairPlacement?'Choose where this wire runs':repairEndpoint!=null?`${repairEndpoint===0?'Start':'End'} point is not connected`:'Connection confirmation is missing'}</strong>
              <p>{repairPlacement?'Change the highlighted Wiring placement field to Ceiling or Under floor.':repairEndpoint!=null?'The orange point on the plan is the loose end. Choose its device in the highlighted connection box below, or drag it onto an existing wire.':'Both ends are attached. Confirm them below or use defaults for an estimated connection.'}</p>
              {!studioBOM?.planning?.material_selection?.assumeConnections && <Button data-connection-defaults disabled={!canEdit || saveState.status==='assuming' || !studioBOM?.planning} onClick={useConnectionDefaults}>Use defaults for estimated pricing</Button>}
              {!repairPlacement && repairEndpoint==null && selectedEntity.assignment_state==='unresolved' && <Button variant="outline" disabled={!canEdit} onClick={()=>updateSelected({...selectedEntity,assignment_state:null})}>Confirm these connections</Button>}
            </div>}
            <details open={focusWireHeight || undefined}><summary>Wire height &amp; circuit</summary>
            <WireHeightEditor key={`${selectedEntity.id}:${(measurementFocus.targets || measurementTargets).join(',')}`} draft={draft} wire={selectedEntity} groupIds={measurementFocus.targets || measurementTargets} defaultHeight={measurements.values?.floor_to_ceiling_height_meters ?? state.record.routing_context?.ceiling_height_meters} focus={focusWireHeight} onApply={next=>editWireNetwork(()=>next)}/>
            <label>Number of separate wires (not cable cores)<input type="number" min="1" max="1000" step="1" value={selectedEntity.conductor_count ?? ''}
              onChange={e=>{const value=e.target.value==='' ? null:Number(e.target.value);if(value===null || Number.isInteger(value)&&value>=1&&value<=1000)updateSelected({...selectedEntity,conductor_count:value})}}/></label>
            <small>Only multiply separate single-core wires. A multi-core cable is counted once.</small>
            <label>Circuit name<input value={selectedEntity.circuit_id ?? ''} maxLength="80"
              onChange={event => updateSelected({...selectedEntity,circuit_id:event.target.value || null})} /></label>
            </details>
            <WireJunctionEditor key={selectedEntity.id} wire={selectedEntity} draft={draft}
              disabled={saveState.status === 'saving' || selectedEntity.disposition === 'rejected'} onEdit={editWireNetwork} />
            {selectedEntity.assignment_state==='unresolved' && <p role="note">{studioBOM?.planning?.material_selection?.assumeConnections?'Estimated connection · existing routing defaults are used for the BOM.':'Suggested connection · use the estimate option in Material prices or connect its endpoints.'}</p>}
            <label className={repairPlacement?'wiring-setting-attention':undefined}>Wiring placement<select data-wire-placement autoFocus={repairPlacement} value={selectedEntity.installation_method || 'unknown'}
              onChange={event => updateSelected(withWiringMethod(selectedEntity,event.target.value))}>
              <option value="unknown" disabled>Not specified</option>
              <option value="concealed_in_ceiling">Ceiling</option>
              <option value="concealed_under_floor">Under floor</option>
            </select></label>
            <p>{selectedEntity.origin === 'generated' ? 'Suggested route' : selectedEntity.path_origin === 'manual' ? 'Drawn path' : 'Traced from plan'}</p>
            {state.record.candidate.payload.observed_routes?.connections?.filter(c => c.from_ref===`segment:${selectedEntity.id}` && c.ambiguity==='ambiguous').map(c =>
              <p role="note" key={c.id}>Unresolved contact: {c.to_ref.replace('symbol:','')} · overlapping or ambiguous device port. Edit the connection rather than guessing.</p>)}
            <p>Drag a blue endpoint near a device or path. Release when it turns green to connect.</p>
            <WireDeviceConnections wire={selectedEntity} draft={draft} presentations={presentations}
              focus={focusWiring && !repairPlacement && repairEndpoint!=null} focusEndpoint={repairEndpoint}
              disabled={saveState.status === 'saving' || selectedEntity.disposition === 'rejected'}
              onConnect={(index,snap) => moveWirePoint(selectedEntity.id,index,snap.point,snap)}
              onDetach={index => updateSelected({...selectedEntity,
                auto_connect_disabled_endpoints:[...new Set([...(selectedEntity.auto_connect_disabled_endpoints || []),index])],
                device_attachments:(selectedEntity.device_attachments || []).filter(a => a.point_index !== index)})} />
            <details><summary>Exact drawing positions</summary><small>Adjust bend points by number instead of dragging them.</small>
              {selectedEntity.points.map((point,index) => <NumericPoint key={index} label={`Wire point ${index+1}`} value={point}
                onChange={p => moveWirePoint(selectedEntity.id,index,p)} />)}
            </details>
            <details><summary>Building-level height · advanced</summary><small>Height from the project’s fixed reference, used for routing between floors.</small><label>Project-reference height (m)<input type="number" min="-1000" max="10000" step="0.1" value={selectedEntity.elevation_meters ?? ''}
              onChange={e => { const value = e.target.value === '' ? null : Number(e.target.value)
                if (value === null || (Number.isFinite(value) && value >= -1000 && value <= 10000)) updateSelected({ ...selectedEntity, elevation_meters: value }) }} /></label>
            <small>Existing absolute elevations are preserved. Relative routing height takes priority when explicitly entered.</small></details>
            <Button variant="outline" onClick={() => updateSelected({ ...selectedEntity, disposition: 'rejected' })}>Remove wiring</Button>
          </>}
          {selected.kind === 'room' && <>
            <label>Room name<input value={selectedEntity.name || ''} maxLength="255" onChange={(event) => updateSelected({ ...selectedEntity, name: event.target.value || null })} /></label>
            <RoomMeasurementSummary room={selectedEntity} pixelsPerMeter={state.record.routing_context?.pixels_per_meter} unit={preferences.units==='imperial'?'ft':'m'}/>
            <details><summary>Edit room outline</summary><div className="demo-room-points">{selectedEntity.boundary.map((point, index) => <NumericPoint key={`${selectedEntity.id}-${index}`} label={`Corner ${index + 1}`} value={point} onChange={(nextPoint) => updateSelected({ ...selectedEntity, boundary: selectedEntity.boundary.map((item, pointIndex) => pointIndex === index ? nextPoint : item) })} />)}</div></details>
            <Button variant="outline" onClick={() => updateSelected({ ...selectedEntity, disposition: 'rejected' })}>Remove room</Button>
          </>}
          {selected.kind === 'symbol' && <>
            {presentations[selectedEntity.id].gangProposal?.basis==='user_requested_default' && <div>
              <p role="note" className="studio-device-provenance">{selectedEntity.gang_count_confirmed ? 'Switch class correction recorded.' : 'Assumed gang count: confirm the switch class before final approval.'}</p>
              {!selectedEntity.gang_count_confirmed && <Button variant="outline" disabled={!selectedEntity.symbol_legend_id}
                onClick={()=>updateDeviceType({symbol_legend_id:selectedEntity.symbol_legend_id,gang_count_confirmed:true})}>Record switch class correction</Button>}
            </div>}
            {presentations[selectedEntity.id].trainingLegend && <details className="studio-device-provenance"><summary>Detection reference</summary>
              Trained legend: {presentations[selectedEntity.id].trainingLegend.name}<br />
              Drawing entry: {presentations[selectedEntity.id].trainingLegend.legend_entry} · Model class {presentations[selectedEntity.id].trainingLegend.model_class_id}
              {!presentations[selectedEntity.id].mapped && <p>No unique active catalog match for this drawing entry.</p>}
            </details>}
            <NumericPoint label="Symbol center (source pixels)" value={selectedEntity.center} onChange={(center) => updateSymbol({ ...selectedEntity, center })} />
            <label>Device symbol<select value={selectedEntity.symbol_legend_id || ''} onChange={(event) => updateDeviceType({symbol_legend_id: event.target.value ? Number(event.target.value) : null,custom_unit_price:null,
              ...(presentations[selectedEntity.id].gangProposal?.basis==='user_requested_default' ? {gang_count_confirmed:Boolean(event.target.value)} : {})})}>
              <option value="">Unmapped</option>{groupLegendChoices(state.legends, { selectedId: selectedEntity.symbol_legend_id }).map((legend) => <option key={legend.id} value={legend.id} disabled={isWiringLegend(legend)}>{legend.class_id} — {legend.displayName}{isWiringLegend(legend) ? ' — Wiring reference, not a device' : ''}</option>)}
            </select></label>
            <details open={focusDeviceHeight || undefined}><summary>Device height &amp; wall</summary>
            <label>Height above floor (m, optional)<input data-device-height autoFocus={focusDeviceHeight} type="number" min="0" max="100" step="0.01"
              value={selectedEntity.mounting_height_meters ?? ''} onChange={event => {
                const value = event.target.value === '' ? null : Number(event.target.value)
                if (value === null || (Number.isFinite(value) && value >= 0 && value <= 100)) updateSymbol({...selectedEntity,mounting_height_meters:value,mounting_reference:selectedEntity.mounting_reference || (selectedEntity.mounting_height_meters==null ? 'device_center':'legacy_unspecified'),mounting_height_source:'designer'})
              }} /></label>
            <label>Measure the height to<select value={selectedEntity.mounting_reference || 'legacy_unspecified'} onChange={event=>updateSymbol({...selectedEntity,mounting_reference:event.target.value,mounting_height_source:'designer'})}>
              <option value="device_center">Device center above finished floor</option><option value="box_bottom">Box bottom above finished floor</option><option value="connection_terminal">Connection terminal above finished floor</option><option value="legacy_unspecified">Previous reference not recorded</option>
            </select></label>
            <label>Wire connection above / below this point (m)<input type="number" min="-10" max="10" step="0.001" value={selectedEntity.terminal_offset_meters ?? ''}
              onChange={event=>{const value=event.target.value==='' ? null:Number(event.target.value);if(value===null || Number.isFinite(value)&&Math.abs(value)<=10)updateSymbol({...selectedEntity,terminal_offset_meters:value})}} /></label>
            <small>Positive is above; negative is below. Leave blank if the wire connects at the height entered.</small>
            <label>Mounting wall (optional)<select value={selectedEntity.mounting_wall_id ?? ''}
              onChange={event => updateSymbol({...selectedEntity,mounting_wall_id:event.target.value || null})}>
              <option value="">Not specified</option>{orderNamed(draft.walls.filter(w => w.disposition !== 'rejected'),w => w.id)
                .map(w => <option key={w.id} value={w.id}>{w.id}</option>)}
            </select></label>
            <Button variant="outline" disabled={!draft.wirings.some(w => w.disposition!=='rejected' && (w.device_attachments || []).some(a => a.symbol_id === selectedEntity.id))}
              onClick={() => pushDraft(detachDevice(draft,selectedEntity.id))}>Detach from wiring</Button></details>
            <label>Custom device unit price (PHP, optional)<input type="number" min="0" max="1000000000" step="0.01"
              value={selectedEntity.custom_unit_price ?? ''} onChange={event => {
                const value = event.target.value === '' ? null : Number(event.target.value)
                if (value === null || (Number.isFinite(value) && value >= 0 && value <= 1000000000)) updateDeviceType({custom_unit_price:value})
              }} /></label>
            <p className="studio-device-provenance">Price per device, applied to matching devices. Live BOM updates automatically; save to retain edits. Admin prices are unchanged.</p>
            <Button variant="outline" className="studio-remove-device" disabled={selectedEntity.disposition === 'rejected'} onClick={() => removeSymbol(selectedEntity.id)}><Trash2 aria-hidden="true" />Remove device</Button>
          </>}
        </fieldset>}
        {!selectedEntity && <p className="studio-inspector-empty">Select an item to edit.</p>}
      </WorkspacePanel>}
      {canEdit && productItem && !(studioShowcase && view==='3d') && <WorkspacePanel title="Product settings" className="demo-review-tools workspace-product-panel" open onOpenChange={closeProduct}><h2>{productKind==='symbol'?presentations[productItem.id]?.name:'Wiring product'}</h2><small>{productItem.id}</small>{studioBOM?.planning?<WorkspaceProductEditor key={`${productKind}:${productItem.id}:${studioBOM.planning.material_selection_revision}:${measurementAction}`} projectId={projectId} floorPlanId={floorPlanId} candidateRunId={state.record.candidate_run_id} item={productItem} kind={productKind} planning={studioBOM.planning} focusField={measurementAction?.startsWith('product-')?measurementAction.slice(8):productKind==='symbol'?'device':'wire'} onClose={closeProduct} onSaved={()=>{setScaleRevision(n=>n+1);setSaveState({status:'idle',message:'Product saved. BOM updated.'})}}/>:<p role="status">Loading compatible products…</p>}<Button variant="ghost" onClick={()=>openMaterialDefaults()}>Plan material defaults</Button></WorkspacePanel>}
      {canEdit && materialField && !(studioShowcase && view==='3d') && <WorkspacePanel title="Plan material defaults" className="demo-review-tools workspace-product-panel" open onOpenChange={closeMaterialDefaults}><h2>Plan material defaults</h2><p>Defaults for this plan. Individual device and wiring choices take priority.</p>{studioBOM?.planning?<><ManualBOMSettings key={studioBOM.planning.material_selection_revision} options={studioBOM.planning} values={studioBOM.planning.material_selection} focusField={materialField} disabled={saveState.status==='pricing'} onChange={savePlanMaterials}/><IndividualPriceEditor projectId={projectId} floorPlanId={floorPlanId} onSaved={()=>setScaleRevision(n=>n+1)}/></>:<p role="status">Loading material settings…</p>}</WorkspacePanel>}

      </div>
      </ViewportFrame>
      <DraftSubmission projectId={projectId} floorPlanId={floorPlanId} revision={state.record.review?.revision_number} designer={session?.user?.role==='DESIGNER'} onSave={()=>saveReview({draftOnly:true})}/>
      {checkWiring && <WiringCheckPanel draft={draft} candidate={state.record.candidate} onClose={()=>setCheckWiring(false)} onSelect={selectItem} onRepair={id=>openScale('wiring',id)} onRemoveDuplicate={canEdit?id=>editWireNetwork(current=>applyWireEdits(current,current.wirings.map(w=>w.id===id?{...w,disposition:'rejected'}:w))):undefined} onRestorePanel={canEdit?id=>editWireNetwork(current=>applyWireEdits(current,current.wirings.map(w=>w.id===id?{...w,disposition:'unresolved'}:w))):undefined} estimateConnections={Boolean(studioBOM?.planning?.material_selection?.assumeConnections)}/>}
      <ScalePanel key={state.record.candidate_run_id} open={Boolean(scalePanel)} section={scalePanel}
        draft={draft}
        onOpenChange={open=>setScalePanel(open ? 'scale':null)} model={sheetModel} context={state.record.routing_context}
        canSave={session?.user?.role==='DESIGNER' && saveState.status!=='saving'} onUseRuler={openRuler} onSelectArea={selectPlanArea}
        record={state.record} region={analysisRegion} onRegionChange={setAnalysisRegion} onFreezeRegion={()=>setTool('select')}
        projectId={projectId} projectFloorId={projectFloorId} floorPlanId={floorPlanId} unsaved={unsaved}
        onSaveDraft={()=>saveReview({draftOnly:true})}/>
      <section id="plan-bom" className="studio-review-estimation" aria-label="Plan estimation">
        <BOMPanel projectId={projectId} floorPlanId={floorPlanId} processingJobId={state.record.processing_job_id}
          onBOMChange={setStudioBOM}
          onEditWorkspaceMaterials={openMaterialDefaults}
          designer={session?.user?.role === 'DESIGNER'}
          unsaved={Boolean(draft && state.record && JSON.stringify(draft) !== JSON.stringify(initialDraft(state.record,state.legends)))}
          draftPreview={bomPreview}
          onUseRuler={openRuler} onEditScale={openScale}
          refreshKey={`${state.record.review?.revision_number || 0}:${scaleRevision}`} />
      </section>
    </article>
  )
}
