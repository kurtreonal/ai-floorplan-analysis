import { Canvas, events } from '@react-three/fiber'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { studioBounds } from './studioBounds.js'
import { useUserPreferences } from '../settings/useUserPreferences.js'
import './studio3d.css'
import { studioProductRows,studioAsset } from './studioAssets.js'
import {StudioQuality} from './StudioQuality.jsx'
import { StudioEnvironment } from './StudioEnvironment.jsx'
import { devicePlacement } from './devicePlacement.js'
import { ViewportFullscreenButton } from '../../components/ViewportFrame.jsx'

import { ViewerCameraControls } from './ViewerCameraControls.jsx'
import { CanonicalScene } from './CanonicalScene.jsx'
import { RouteLines3D } from '../routing/RouteLines3D.jsx'
import { DraftWiring3D } from './DraftWiring3D.jsx'
import { routeDeviceConnectors } from './routeDeviceConnectors.js'
import { WiringTargetChooser } from '../detection-review/WiringTargetChooser.jsx'
import { WiringTargetMarker3D } from './WiringTargetMarker3D.jsx'
import { DrawingPlane3D } from './DrawingPlane3D.jsx'
import { SpatialDrawingControls } from './SpatialDrawingControls.jsx'
import { selectionGesture } from './selectionGesture.js'

function studioEvents(state) {
  const isDevice=hit=>{
    for(let object=hit.object;object;object=object.parent)if(object.userData?.vedDeviceId)return true
    return false
  }
  // Products are deliberately visible through walls, so their hit order must
  // agree with that presentation. Keep depth order among the devices intact.
  return {...events(state),filter:hits=>hits.map((hit,index)=>({hit,index,device:isDevice(hit)}))
    .sort((a,b)=>Number(b.device)-Number(a.device) || a.index-b.index).map(item=>item.hit)}
}

export function Viewer3DCanvas({ controlsRef, onControlsReady, scene, showRoof = false, routeSegments = [], inspectUnderground = false, selectedSymbolId, onSelectSymbol, onSelectWall, onMoveSymbol, selectedWireId, selectedWallId, onSelectWire, onMoveWirePoint, onFindWireDeviceSnap, presentations = {}, navigationMode = 'select',drawing=null,floorElevation=null,projectLabel='VED plan',estimated=false,bom,onShowcaseChange,readOnlyPresentation=false,onEditProduct,productEditorOpen=false,onInspectItem }) {
  const products=useMemo(()=>studioProductRows(bom),[bom])
  const {preferences,updatePreferences}=useUserPreferences()
  const [showcase,setShowcase]=useState(readOnlyPresentation)
  const [inspectWiring,setInspectWiring]=useState(false)
  const [visibility,setVisibility]=useState({architecture:true,devices:true,wiring:true,roof:showRoof})
  const [exportError,setExportError]=useState('')
  const [revealed,setRevealed]=useState(false)
  const [focusNetwork,setFocusNetwork]=useState(false)
  const renderer=useRef(null)
  const internalControls=useRef(null)
  const cameraControls=controlsRef || internalControls
  const bounds=useMemo(()=>studioBounds(scene),[scene])
  const wallMode=revealed ? 'xray' : preferences.studioWalls === 'xray' ? 'xray' : 'full'
  const grid=preferences.studioGrid ?? false
  const selectedDevice=scene?.symbols?.find(s=>s.id===selectedSymbolId)
  const selectedPosition=selectedDevice && devicePlacement(selectedDevice,scene,selectedDevice.presentation?.family || 'unknown').position
  const selectedWire=scene?.draftWires?.find(w=>w.id===selectedWireId)
  const technical=!showcase || inspectWiring
  async function exportImage() {
    const state=renderer.current
    if (!state) return
    try {
      state.gl.render(state.scene,state.camera)
      const source=state.gl.domElement
      const factor=Math.min(1,2048/Math.max(source.width,source.height))
      const output=document.createElement('canvas')
      output.width=Math.round(source.width*factor);output.height=Math.round(source.height*factor)
      const ctx=output.getContext('2d')
      ctx.drawImage(source,0,0,output.width,output.height)
      ctx.fillStyle='rgba(255,252,246,.95)';ctx.fillRect(0,output.height-48,output.width,48)
      ctx.fillStyle='#27363a';ctx.font='14px sans-serif'
      ctx.fillText(`${projectLabel} · Planning visualization${estimated ? ' · Estimated' : ''}`,16,output.height-19,output.width-32)
      const blob=await new Promise(resolve=>output.toBlob(resolve,'image/png'))
      if (!blob) throw new Error('No image')
      const url=URL.createObjectURL(blob), link=document.createElement('a')
      link.href=url;link.download='VED-studio.png';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
      setExportError('')
    } catch {setExportError('Image export failed. Try again in a WebGL-enabled browser.')}
  }
  const [draggingDevice, setDraggingDevice] = useState(false)
  const [pendingTarget,setPendingTarget] = useState(null)
  const handleDragging = useCallback(dragging => {
    setDraggingDevice(dragging)
    if (dragging) setPendingTarget(null)
  }, [])
  const activeTarget = !showcase && pendingTarget && pendingTarget.scene === scene && pendingTarget.selectionId === selectedWireId
    && navigationMode === 'transform' && !drawing?.active ? pendingTarget : null
  const gesture = useRef(selectionGesture())
  const moving = !showcase && navigationMode === 'transform' && !drawing?.enabled
  const editing = !showcase && (moving || drawing?.enabled || ['draw','wire','place-device','region'].includes(navigationMode))
  const selectable = !showcase && ['select','transform'].includes(navigationMode) && !drawing?.enabled
  const effectiveFly = !editing
  useEffect(() => {
    const cancel = () => gesture.current.cancel()
    const escape = event => { if (event.key === 'Escape') cancel() }
    window.addEventListener('blur',cancel); window.addEventListener('keydown',escape)
    return () => { cancel(); window.removeEventListener('blur',cancel); window.removeEventListener('keydown',escape) }
  },[])
  const selectSymbol = (id,event) => {
    if (!gesture.current.canSelect(event)) return
    onSelectSymbol?.(id)
    // Only a direct click focuses the camera; dragging/orbiting and list selection do not.
    if (navigationMode !== 'select') return
    const symbol=scene?.symbols?.find(item=>item.id===id)
    if (!symbol) return
    const family=symbol.presentation?.family || 'unknown'
    const placement=devicePlacement(symbol,scene,family)
    const unit=scene.unitsPerMeter ?? 1
    const normal=[Math.sin(placement.rotation),Math.cos(placement.rotation)]
    const approach=placement.mount==='wall' ? [normal[0]*1.1+normal[1]*.18,.18,normal[1]*1.1-normal[0]*.18]
      : placement.mount==='ceiling' ? [.8,-.7,.8] : [1,.8,1]
    const distance=(['linear-light','troffer'].includes(family)?2:family==='panel'?1.4:.85)*unit
    cameraControls.current?.focus(placement.position,distance,approach)
  }
  const selectWire = (id,event) => { if (gesture.current.canSelect(event)) onSelectWire?.(id) }
  const selectWall = (id,event) => { if (gesture.current.canSelect(event)) onSelectWall?.(id) }
  const fallback = (
    <div className="viewer-3d-webgl-fallback" role="status">
      Interactive 3D plan showing architecture, devices and wiring. Choose Edit 2D for the drawing view.
    </div>
  )

  return (
    <section
      className="viewer-3d-canvas"
      aria-label="3D viewer"
      tabIndex={0}
      onPointerDownCapture={event => {
        if (event.target.closest?.('input,textarea,select,button')) return
        event.currentTarget.focus({ preventScroll: true }); gesture.current.down(event)
      }}
      onPointerMoveCapture={event=>gesture.current.move(event)}
      onPointerUpCapture={event=>{
        const bounds=event.currentTarget.querySelector('canvas')?.getBoundingClientRect()
        gesture.current.up(event,!bounds || event.clientX>=bounds.left && event.clientX<=bounds.right && event.clientY>=bounds.top && event.clientY<=bounds.bottom)
      }}
      onPointerCancelCapture={()=>gesture.current.cancel()}
      onLostPointerCapture={event=>gesture.current.lost(event)}
    >
      <ViewportFullscreenButton />
      <div className="ved-studio-toolbar" aria-label="3D Studio controls">
        {!readOnlyPresentation && <div role="group" aria-label="Presentation mode">
          <button type="button" aria-pressed={!showcase} onClick={()=>{setShowcase(false);onShowcaseChange?.(false)}}>Design</button>
          <button type="button" aria-pressed={showcase} disabled={Boolean(drawing?.active || draggingDevice)} onClick={()=>{setShowcase(true);onShowcaseChange?.(true)}}>Showcase</button>
        </div>}
        <div role="group" aria-label="Studio camera">
          <select aria-label="Camera preset" defaultValue="isometric" onChange={e=>cameraControls.current?.[e.target.value]?.()}>
            <option value="isometric">Isometric</option><option value="top">Top</option><option value="front">Front</option>
          </select>
          <button type="button" onClick={()=>cameraControls.current?.fit()}>Fit model</button>
          {(selectedDevice || selectedWire) && <button type="button" onClick={()=>cameraControls.current?.focus(selectedPosition || selectedWire?.points[0])}>Focus selection</button>}
        </div>
        <details><summary>Visibility</summary><div className="ved-studio-visibility">
          <label>Walls<select aria-label="Studio wall visibility" value={wallMode} onChange={e=>{setRevealed(false);updatePreferences({studioWalls:e.target.value})}}><option value="full">Full walls</option><option value="xray">X-ray walls</option></select></label>
          {Object.entries(visibility).map(([key,value])=><label key={key}><input type="checkbox" checked={value} onChange={e=>setVisibility(v=>({...v,[key]:e.target.checked}))}/>{key==='roof' ? 'Illustrative ceiling' : key}</label>)}
          <label><input type="checkbox" checked={grid} onChange={e=>updatePreferences({studioGrid:e.target.checked})}/>Grid</label>
        </div></details>
        {showcase && <><button type="button" aria-pressed={inspectWiring} onClick={()=>setInspectWiring(v=>!v)}>Inspect wiring</button><button type="button" onClick={exportImage}>Export PNG</button></>}
      </div>
      {exportError && <p className="ved-studio-notice" role="alert">{exportError}</p>}
      {readOnlyPresentation && estimated && <span className="ved-studio-estimated" role="status">Illustrative 3D scale</span>}
      {technical && visibility.wiring && <div className="ved-studio-legend" aria-label="Wiring legend"><span>● Ceiling / service</span><span>● Under floor</span><span>● Unresolved</span><small>Display thickness only</small></div>}
      {!showcase && !productEditorOpen && selectedDevice && <aside className="ved-studio-inspector" aria-label="Selected device">
        <strong>{selectedDevice.presentation?.label || selectedDevice.classification?.name || selectedDevice.id}</strong>
        <small title="Illustrative visual only. The priced product and connection terminals are unchanged; a procedural preview is used if loading fails.">{studioAsset(selectedDevice,products[selectedSymbolId])?.status || 'Representative model'}</small>
        {products[selectedSymbolId] ? <><span>{products[selectedSymbolId].client_product_name || products[selectedSymbolId].material_name || 'No priced product assigned'}</span>
          <small>{products[selectedSymbolId].unit_price!=null ? `${products[selectedSymbolId].currency || ''} ${products[selectedSymbolId].unit_price} / ${products[selectedSymbolId].unit}` : 'Price unavailable'} · backend takeoff</small></> : <small>Price details unavailable for this view.</small>}
        <button type="button" onClick={()=>setRevealed(v=>!v)}>{revealed ? 'Restore walls' : 'Reveal through walls'}</button>
        {onInspectItem && <button type="button" onClick={()=>onInspectItem({kind:'symbol',id:selectedSymbolId})}>More device settings</button>}
        {onEditProduct && <button type="button" onClick={()=>{onEditProduct({kind:'symbol',id:selectedSymbolId})}}>Change brand / product</button>}
      </aside>}
      {!showcase && !productEditorOpen && selectedWire && <aside className="ved-studio-inspector" aria-label="Selected wiring">
        {onInspectItem && <button type="button" onClick={()=>onInspectItem({kind:'wiring',id:selectedWireId})}>More wiring settings</button>}
        <strong>{selectedWire.id}</strong><small>{selectedWire.networkId ? `Network ${selectedWire.networkId}` : 'Selected path'}</small>
        <button type="button" aria-pressed={focusNetwork} onClick={()=>{setFocusNetwork(v=>!v);cameraControls.current?.focus(selectedWire.points[0])}}>Focus network</button>
        {onEditProduct && <button type="button" onClick={()=>{onEditProduct({kind:'wiring',id:selectedWireId})}}>Change wiring product</button>}
      </aside>}
      <Canvas
        events={studioEvents}
        shadows
        onCreated={state=>{state.gl.localClippingEnabled=true;renderer.current=state}}
        camera={{ position: [bounds.target[0]+bounds.extent,bounds.target[1]+bounds.extent*.85,bounds.target[2]+bounds.extent], fov: 42, near: 0.01, far: bounds.extent*30 }}
        fallback={fallback}
        frameloop="demand"
        dpr={[1, 1.5]}
      >
        <color attach="background" args={['#e9edef']} />
        <StudioQuality/>
        <StudioEnvironment/>
        <hemisphereLight intensity={1.1} color="#f6f8ff" groundColor="#777e83" />
        <directionalLight castShadow position={[bounds.target[0]+bounds.extent*.4,bounds.target[1]+bounds.extent*1.5,bounds.target[2]+bounds.extent*.6]}
          target-position={bounds.target} intensity={2.1} color="#fff7eb" shadow-mapSize={[2048,2048]}
          shadow-camera-left={-bounds.extent} shadow-camera-right={bounds.extent} shadow-camera-top={bounds.extent} shadow-camera-bottom={-bounds.extent}
          shadow-camera-far={bounds.extent*5} shadow-normalBias={.015} shadow-bias={-.0001} />
        <directionalLight position={[-10, 8, -5]} intensity={.6} color="#e2eaf5" />
        {scene && <CanonicalScene scene={scene} showRoof={visibility.roof} bounds={bounds} wallMode={wallMode} products={products}
          showArchitecture={visibility.architecture} showDevices={visibility.devices} showWiring={visibility.wiring}
          selectedWallId={showcase ? null : selectedWallId} selectedSymbolId={showcase ? null : selectedSymbolId}
          onSelectSymbol={selectable ? selectSymbol : undefined} onSelectWall={selectable ? selectWall : undefined}
          onMoveSymbol={moving ? onMoveSymbol : undefined} onDraggingChange={handleDragging} />}
        <RouteLines3D segments={visibility.wiring ? [...routeSegments, ...routeDeviceConnectors(scene,routeSegments)] : []} inspectUnderground={inspectUnderground || inspectWiring} />
        {scene?.previewOnly && visibility.wiring && <DraftWiring3D scene={scene} technical={technical} focusNetwork={focusNetwork} selectedWireId={showcase ? null : selectedWireId} onSelectWire={selectable ? selectWire : undefined}
          onMoveWirePoint={moving ? onMoveWirePoint : undefined} onFindWireDeviceSnap={onFindWireDeviceSnap}
          onChooseWireTarget={(wireId,index,choices) => setPendingTarget({scene,selectionId:selectedWireId,wireId,index,choices})}
          onDraggingChange={handleDragging} />}
        {activeTarget?.highlighted?.displayPosition && <WiringTargetMarker3D position={activeTarget.highlighted.displayPosition} />}
        {!showcase && drawing?.enabled&&<DrawingPlane3D scene={scene} drawing={drawing} tool={navigationMode} />}
        {grid && <gridHelper position={[bounds.target[0],bounds.floor-.02,bounds.target[2]]} args={[bounds.extent * 2, 20, '#b1b9b9', '#dee1de']} />}
        <ViewerCameraControls ref={cameraControls} onReady={onControlsReady} target={bounds.target} extent={bounds.extent}
          enabled={!draggingDevice && !activeTarget} leftOrbit={!editing}
          panMode={navigationMode === 'pan'} freeFly={effectiveFly} />
      </Canvas>
      {!showcase && drawing&&<SpatialDrawingControls drawing={drawing} tool={navigationMode} floorElevation={floorElevation} presentations={presentations} />}
      {activeTarget && <WiringTargetChooser choices={activeTarget.choices} presentations={presentations}
        onPreview={highlighted=>setPendingTarget(current=>current?{...current,highlighted}:null)}
        onCancel={()=>setPendingTarget(null)} onChoose={target=>{
          const snap = {...target}
          delete snap.displayPosition
          setPendingTarget(null)
          onMoveWirePoint?.(activeTarget.wireId,activeTarget.index,
            {x:snap.point.x*scene.sourceScale,y:snap.point.y*scene.sourceScale},snap)
        }} />}
      <details className="studio-navigation-help"><summary>Navigation <span>Left drag to orbit</span></summary><p>{editing ? 'Middle-drag orbit · right-drag pan · scroll zoom. Finish drawing to use keyboard movement.' : 'Left-drag orbit · right-drag look · middle-drag pan · scroll zoom. Click the scene, then use WASD / arrows to move, Q/E to descend/rise, Shift to move faster. Click without dragging to select.'}</p></details>
    </section>
  )
}
