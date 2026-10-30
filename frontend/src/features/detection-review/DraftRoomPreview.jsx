import { useMemo, useRef,useEffect,useCallback } from 'react'
import { Viewer3DCanvas } from '../viewer-3d/Viewer3DCanvas.jsx'
import { Viewer3DErrorBoundary } from '../viewer-3d/Viewer3DErrorBoundary.jsx'
import { buildDraftRoomScene } from './draftRoomScene.js'
import { Button } from '../../components/ui/button.jsx'
import { Settings2 } from 'lucide-react'
import './planInformation.css'
import { clampDevicePoint } from './devicePresentation.js'
import { findWireEndpointSnap, findWireEndpointTargets } from './wirePathSnap.js'
import { useUserPreferences } from '../settings/useUserPreferences.js'
import { useSpatialDrawing } from '../viewer-3d/useSpatialDrawing.js'
import {devicePlacement} from '../viewer-3d/devicePlacement.js'

export function DraftRoomPreview({ draft, layers, width, height, projectId, presentations, selected, onSelect, onUpdateSymbol, onMoveWirePoint, navigationMode, routingContext, visibleRoomId = null,bom,onShowcaseChange,onEditProduct,productEditorOpen,onInspectItem,productEditTarget,
  onAddWire,onAddWall,onDrawingPendingChange,onToolChange,onOpenMeasurements,editingSession=0,setupRevision=0,drawingWireMethod='unknown',drawingDisabled=false }) {
  const { preferences } = useUserPreferences()
  const controlsRef = useRef(null)
  const wallHeight=routingContext?.ceiling_height_meters ?? 3
  const longSideMeters=40 // Legacy preview framing only; never a scale input.
  const confirmedScale=routingContext?.pixels_per_meter
  const measuredLength=Number.isFinite(confirmedScale)&&confirmedScale>0 ? Math.max(width,height)/confirmedScale : null
  const result = useMemo(() => {
    try {
      const scene = buildDraftRoomScene({...draft, rooms:draft.rooms.filter(room => layers.rooms && room.id === visibleRoomId)}, width, height, wallHeight * 10 / (measuredLength??longSideMeters), presentations,
        { longSideMeters, pixelsPerMeter:confirmedScale, floorElevationMeters:routingContext?.floor_elevation_meters,
          serviceHeightAboveFloor:routingContext?.service_height_above_floor_meters,mountingDefaults:routingContext?.mounting_defaults,
          automaticHeights:routingContext?.height_mode==='automatic',
          planningMountingHeights:routingContext?.mounting_defaults })
      return { scene: { ...scene, walls: layers?.walls === false ? [] : scene.walls,
        roofRooms: scene.rooms, rooms: layers?.rooms === false ? [] : scene.rooms, symbols: layers?.symbols === false ? [] : scene.symbols,
        draftWires: layers?.wirings === false ? [] : scene.draftWires } }
    }
    catch (error) { return { error: error.message } }
  }, [draft, layers, width, height, wallHeight, longSideMeters, presentations, routingContext,measuredLength,confirmedScale,visibleRoomId])
  const drawing=useSpatialDrawing({tool:navigationMode,scene:result.scene,draft,context:routingContext,presentations,
    method:drawingWireMethod,editingSession,onAddWire,onAddWall,onPendingChange:onDrawingPendingChange,onToolChange,
    snapping:preferences.snapping,disabled:drawingDisabled,setupRevision})
  const unmeasuredDevices = new Set(result.scene?.draftWires.flatMap(w => w.unmeasuredDeviceIds) || [])
  const focusedProduct=useRef({key:null,point:null,last:null})
  const productPoint=useMemo(()=>{
    const scene=result.scene
    if(!scene || !productEditTarget)return null
    const unit=scene.unitsPerMeter ?? 1
    const symbol=scene.symbols.find(s=>s.id===productEditTarget.id)
    const family=symbol?.presentation?.family || 'unknown'
    if(!symbol)return {point:scene.draftWires.find(w=>w.id===productEditTarget.id)?.points[0],distance:3*unit}
    const placement=devicePlacement(symbol,scene,family)
    const normal=[Math.sin(placement.rotation),Math.cos(placement.rotation)]
    return {point:placement.position,distance:(['linear-light','troffer'].includes(family)?2:family==='panel'?1.4:.75)*unit,
      approach:placement.mount==='wall'?[normal[0]*1.1+normal[1]*.18,.18,normal[1]*1.1-normal[0]*.18]:placement.mount==='ceiling'?[.8,-.7,.8]:[1,.8,1]}
  },[result.scene,productEditTarget])
  const focusProduct=useCallback(ready=>{
    if(ready===false){focusedProduct.current.last=null;return}
    const current=focusedProduct.current,controls=controlsRef.current
    if(current.key && current.point?.point && controls?.focus && current.last!==current.key){controls.focus(current.point.point,current.point.distance,current.point.approach);current.last=current.key}
  },[])
  useEffect(()=>{
    focusedProduct.current.key=productEditTarget?.id || null
    focusedProduct.current.point=productPoint
    if(!productEditTarget)focusedProduct.current.last=null
    focusProduct()
  },[productEditTarget,productPoint,focusProduct])
  return <section aria-label="Unfinished room preview">
    <div className="studio-preview-overlay">
    <details className="studio-preview-dimensions"><summary><Settings2 size={16} aria-hidden="true" />3D settings</summary>
      <p>Preview dimensions are illustrative unless a confirmed scale and saved elevations are available. They do not approve or calibrate this plan.</p>
      {unmeasuredDevices.size>0 && <p role="note">Unresolved vertical connections remain excluded. Resolve them in Plan measurements or the item inspector.</p>}
      <p>Ceiling height: {wallHeight} m {routingContext?.height_mode==='automatic' ? '· planning default':'· custom / illustrative'}</p>
      <Button variant="outline" onClick={onOpenMeasurements}>Plan measurements</Button>
      {measuredLength!=null&&<p>{routingContext?.estimated ? 'Estimated measurement basis is active.' : routingContext?.measurement_state==='known_reference' ? 'Known-reference scale is active.':'Source-sheet scale is active.'} Per-wall dimensions override illustrative defaults.</p>}
      <p>Dimensions and route heights come from Plan measurements. Roof cover and equipment sizes remain illustrative.</p>
    </details>
    {(routingContext?.estimated || routingContext?.height_basis==='assumed' || measuredLength==null) && <small className="measurement-basis" role="status">{measuredLength==null ? 'Illustrative preview':'Estimated · planning assumptions'}</small>}
    </div>
    {result.error ? <p role="alert">{result.error}</p> : !drawing.active && !drawing.keepCanvas && result.scene.rooms.length === 0 && result.scene.walls.length === 0 && result.scene.symbols.length === 0 && result.scene.draftWires.length === 0 ? <p>No geometry yet. Return to 2D to add walls, devices or wiring.</p> :
      <Viewer3DErrorBoundary projectId={projectId} title="Draft 3D preview unavailable">
        <Viewer3DCanvas scene={result.scene} controlsRef={controlsRef} projectLabel={`VED project ${projectId}`}
          bom={bom}
          onControlsReady={focusProduct}
          onEditProduct={onEditProduct} productEditorOpen={productEditorOpen} onInspectItem={onInspectItem}
          onShowcaseChange={onShowcaseChange}
          estimated={Boolean(routingContext?.estimated || routingContext?.height_basis==='assumed' || measuredLength==null)}
          drawing={drawing} floorElevation={routingContext?.floor_elevation_meters}
          selectedWireId={selected?.kind === 'wiring' ? selected.id : null}
          selectedWallId={selected?.kind === 'wall' ? selected.id : null}
          onSelectWire={(id) => onSelect?.({ kind: 'wiring', id })}
          presentations={presentations}
          onFindWireDeviceSnap={(id,index,point,distanceToSymbol,threshold,distanceToPath,allTargets=false) =>
            preferences.snapping ? (allTargets ? findWireEndpointTargets : findWireEndpointSnap)(point,id,index,draft,presentations,threshold,distanceToSymbol,distanceToPath) : allTargets ? [] : null}
          onMoveWirePoint={navigationMode === 'pan' || !onMoveWirePoint ? undefined : (id,index,point,snap) => {
            const sourcePoint = { x: point.x / result.scene.sourceScale, y: point.y / result.scene.sourceScale }
            if (snap) onMoveWirePoint(id,index,snap.point,snap)
            else onMoveWirePoint(id,index,sourcePoint)
          }}
          selectedSymbolId={selected?.kind === 'symbol' ? selected.id : null} navigationMode={navigationMode}
          onSelectSymbol={(id) => onSelect?.({ kind: 'symbol', id })}
          onSelectWall={id=>onSelect?.({kind:'wall',id})}
          onMoveSymbol={navigationMode === 'pan' || !onUpdateSymbol ? undefined : (id, point) => {
            const symbol = draft.symbols.find((item) => item.id === id)
            const center = clampDevicePoint({ x: point.x / result.scene.sourceScale, y: point.y / result.scene.sourceScale }, width, height)
            if (symbol && center) onUpdateSymbol?.({ ...symbol, center,
              ...(Number.isFinite(point.mountingHeight) ? { mounting_height_meters: point.mountingHeight,
                mounting_reference: 'device_center', mounting_height_source: 'designer',
                mounting_wall_id: point.mountingWallId || null } : {}) })
          }} />
      </Viewer3DErrorBoundary>}
    {result.scene?.invalidSymbolCount > 0 && <p role="alert">{result.scene.invalidSymbolCount} invalid device positions omitted. Correct them in the inspector.</p>}
    {result.scene?.invalidWiringCount > 0 && <p role="alert">{result.scene.invalidWiringCount} invalid wiring traces omitted. Correct their points in the inspector.</p>}
  </section>
}
