import { Canvas } from '@react-three/fiber'
import { useCallback, useState } from 'react'

import { ViewerCameraControls } from './ViewerCameraControls.jsx'
import { CanonicalScene } from './CanonicalScene.jsx'
import { RouteLines3D } from '../routing/RouteLines3D.jsx'
import { DraftWiring3D } from './DraftWiring3D.jsx'
import { routeDeviceConnectors } from './routeDeviceConnectors.js'
import { WiringTargetChooser } from '../detection-review/WiringTargetChooser.jsx'
import { WiringTargetMarker3D } from './WiringTargetMarker3D.jsx'
import { DrawingPlane3D } from './DrawingPlane3D.jsx'
import { SpatialDrawingControls } from './SpatialDrawingControls.jsx'


export function Viewer3DCanvas({ controlsRef, onControlsReady, scene, showRoof = false, routeSegments = [], inspectUnderground = false, selectedSymbolId, onSelectSymbol, onMoveSymbol, selectedWireId, onSelectWire, onMoveWirePoint, onFindWireDeviceSnap, presentations = {}, navigationMode = 'select',drawing=null,floorElevation=null }) {
  const [draggingDevice, setDraggingDevice] = useState(false)
  const [pendingTarget,setPendingTarget] = useState(null)
  const handleDragging = useCallback(dragging => {
    setDraggingDevice(dragging)
    if (dragging) setPendingTarget(null)
  }, [])
  const activeTarget = pendingTarget && pendingTarget.scene === scene && pendingTarget.selectionId === selectedWireId
    && navigationMode !== 'pan' && !drawing?.active ? pendingTarget : null
  const [freeFly, setFreeFly] = useState(true)
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
        if (!event.target.closest?.('input,textarea,select,button')) event.currentTarget.focus({ preventScroll: true })
      }}
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
        {scene && <CanonicalScene scene={scene} showRoof={showRoof} selectedSymbolId={selectedSymbolId} onSelectSymbol={onSelectSymbol}
          onMoveSymbol={drawing?.active?undefined:onMoveSymbol} onDraggingChange={setDraggingDevice} />}
        <RouteLines3D segments={[...routeSegments, ...routeDeviceConnectors(scene,routeSegments)]} inspectUnderground={inspectUnderground} />
        {scene?.previewOnly && <DraftWiring3D scene={scene} selectedWireId={selectedWireId} onSelectWire={onSelectWire}
          onMoveWirePoint={drawing?.active?undefined:onMoveWirePoint} onFindWireDeviceSnap={onFindWireDeviceSnap}
          onChooseWireTarget={(wireId,index,choices) => setPendingTarget({scene,selectionId:selectedWireId,wireId,index,choices})}
          onDraggingChange={handleDragging} />}
        {activeTarget?.highlighted?.displayPosition && <WiringTargetMarker3D position={activeTarget.highlighted.displayPosition} />}
        {drawing?.enabled&&<DrawingPlane3D scene={scene} drawing={drawing} tool={navigationMode} />}
        <gridHelper position={scene?.target} args={[scene ? scene.extent * 2 : 20, 20, '#b1b9b9', '#dee1de']} />
        <ViewerCameraControls ref={controlsRef} onReady={onControlsReady} target={scene?.target} extent={scene?.extent}
          enabled={!draggingDevice && !activeTarget && !drawing?.enabled} panMode={navigationMode === 'pan'} freeFly={freeFly} />
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
      <button className="studio-camera-mode" type="button" aria-pressed={freeFly} onClick={() => setFreeFly(value => !value)}>
        {freeFly ? 'Free fly' : 'Orbit'}
      </button>
      <p className="studio-navigation-hint">{freeFly ? 'Right-drag to look · WASD / arrows to fly · Q/E down/up · Shift sprint' : 'Drag to orbit · scroll to zoom · select Free fly for keyboard movement'} · Wire spacing is display-only.</p>
    </section>
  )
}
