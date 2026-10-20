import { Canvas } from '@react-three/fiber'
import { useCallback, useEffect, useRef, useState } from 'react'

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


export function Viewer3DCanvas({ controlsRef, onControlsReady, scene, showRoof = false, routeSegments = [], inspectUnderground = false, selectedSymbolId, onSelectSymbol, onSelectWall, onMoveSymbol, selectedWireId, selectedWallId, onSelectWire, onMoveWirePoint, onFindWireDeviceSnap, presentations = {}, navigationMode = 'select',drawing=null,floorElevation=null }) {
  const [draggingDevice, setDraggingDevice] = useState(false)
  const [pendingTarget,setPendingTarget] = useState(null)
  const handleDragging = useCallback(dragging => {
    setDraggingDevice(dragging)
    if (dragging) setPendingTarget(null)
  }, [])
  const activeTarget = pendingTarget && pendingTarget.scene === scene && pendingTarget.selectionId === selectedWireId
    && navigationMode === 'transform' && !drawing?.active ? pendingTarget : null
  const [freeFly, setFreeFly] = useState(false)
  const gesture = useRef(selectionGesture())
  const moving = navigationMode === 'transform' && !drawing?.enabled
  const editing = moving || drawing?.enabled || ['draw','wire','place-device','region'].includes(navigationMode)
  const selectable = ['select','transform'].includes(navigationMode) && !drawing?.enabled
  const effectiveFly = freeFly && !editing
  useEffect(() => {
    const cancel = () => gesture.current.cancel()
    const escape = event => { if (event.key === 'Escape') cancel() }
    window.addEventListener('blur',cancel); window.addEventListener('keydown',escape)
    return () => { cancel(); window.removeEventListener('blur',cancel); window.removeEventListener('keydown',escape) }
  },[])
  const selectSymbol = (id,event) => { if (gesture.current.canSelect(event)) onSelectSymbol?.(id) }
  const selectWire = (id,event) => { if (gesture.current.canSelect(event)) onSelectWire?.(id) }
  const selectWall = (id,event) => { if (gesture.current.canSelect(event)) onSelectWall?.(id) }
  const fallback = (
    <div className="viewer-3d-webgl-fallback" role="status">
      This browser could not create the WebGL canvas required for the 3D viewer.
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
      <Canvas
        camera={{ position: scene ? [scene.target[0] + scene.extent, scene.elevation + scene.extent, scene.target[2] + scene.extent] : [8, 6, 8], fov: 50, near: 0.01, far: scene ? scene.extent * 20 : 1000 }}
        fallback={fallback}
        frameloop="demand"
        dpr={[1, 2]}
      >
        <color attach="background" args={['#f3f1ec']} />
        <ambientLight intensity={1.15} />
        <directionalLight position={[10, 20, 10]} intensity={1.7} color="#fff7e9" />
        <directionalLight position={[-10, 8, -5]} intensity={.45} color="#dce6ee" />
        {scene && <CanonicalScene scene={scene} showRoof={showRoof} selectedWallId={selectedWallId} selectedSymbolId={selectedSymbolId}
          onSelectSymbol={selectable ? selectSymbol : undefined} onSelectWall={selectable ? selectWall : undefined}
          onMoveSymbol={moving ? onMoveSymbol : undefined} onDraggingChange={handleDragging} />}
        <RouteLines3D segments={[...routeSegments, ...routeDeviceConnectors(scene,routeSegments)]} inspectUnderground={inspectUnderground} />
        {scene?.previewOnly && <DraftWiring3D scene={scene} selectedWireId={selectedWireId} onSelectWire={selectable ? selectWire : undefined}
          onMoveWirePoint={moving ? onMoveWirePoint : undefined} onFindWireDeviceSnap={onFindWireDeviceSnap}
          onChooseWireTarget={(wireId,index,choices) => setPendingTarget({scene,selectionId:selectedWireId,wireId,index,choices})}
          onDraggingChange={handleDragging} />}
        {activeTarget?.highlighted?.displayPosition && <WiringTargetMarker3D position={activeTarget.highlighted.displayPosition} />}
        {drawing?.enabled&&<DrawingPlane3D scene={scene} drawing={drawing} tool={navigationMode} />}
        <gridHelper position={scene?.target} args={[scene ? scene.extent * 2 : 20, 20, '#b1b9b9', '#dee1de']} />
        <ViewerCameraControls ref={controlsRef} onReady={onControlsReady} target={scene?.target} extent={scene?.extent}
          enabled={!draggingDevice && !activeTarget} leftOrbit={!editing}
          panMode={navigationMode === 'pan'} freeFly={effectiveFly} />
      </Canvas>
      {drawing&&<SpatialDrawingControls drawing={drawing} tool={navigationMode} floorElevation={floorElevation} presentations={presentations} />}
      {activeTarget && <WiringTargetChooser choices={activeTarget.choices} presentations={presentations}
        onPreview={highlighted=>setPendingTarget(current=>current?{...current,highlighted}:null)}
        onCancel={()=>setPendingTarget(null)} onChoose={target=>{
          const snap = {...target}
          delete snap.displayPosition
          setPendingTarget(null)
          onMoveWirePoint?.(activeTarget.wireId,activeTarget.index,
            {x:snap.point.x*scene.sourceScale,y:snap.point.y*scene.sourceScale},snap)
        }} />}
      <button className="studio-camera-mode" type="button" disabled={editing} aria-pressed={effectiveFly} onClick={() => setFreeFly(value => !value)}>
        {effectiveFly ? 'Free fly' : 'Orbit'}
      </button>
      <p className="studio-navigation-hint">{effectiveFly ? 'Right-drag to look · WASD / arrows to fly' : editing ? 'Middle-drag orbit · right-drag pan · scroll zoom' : 'Click selects · left-drag orbits · right-drag pans · scroll zoom'}</p>
    </section>
  )
}
