import { Canvas } from '@react-three/fiber'
import { useState } from 'react'

import { ViewerCameraControls } from './ViewerCameraControls.jsx'
import { CanonicalScene } from './CanonicalScene.jsx'
import { RouteLines3D } from '../routing/RouteLines3D.jsx'


export function Viewer3DCanvas({ controlsRef, onControlsReady, scene, showRoof = false, routeSegments = [], selectedSymbolId, onSelectSymbol, onMoveSymbol, navigationMode = 'select' }) {
  const [draggingDevice, setDraggingDevice] = useState(false)
  const fallback = (
    <div className="viewer-3d-webgl-fallback" role="status">
      This browser could not create the WebGL canvas required for the 3D viewer.
    </div>
  )

  return (
    <section
      className="viewer-3d-canvas"
      aria-label="3D viewer"
    >
      <Canvas
        camera={{ position: scene ? [scene.target[0] + scene.extent, scene.elevation + scene.extent, scene.target[2] + scene.extent] : [8, 6, 8], fov: 50, near: 0.01, far: scene ? scene.extent * 20 : 1000 }}
        fallback={fallback}
        frameloop="demand"
        dpr={[1, 2]}
      >
        <color attach="background" args={['#edf2f6']} />
        <ambientLight intensity={1.2} />
        <directionalLight position={[10, 20, 10]} intensity={2} />
        {scene && <CanonicalScene scene={scene} showRoof={showRoof} selectedSymbolId={selectedSymbolId} onSelectSymbol={onSelectSymbol}
          onMoveSymbol={onMoveSymbol} onDraggingChange={setDraggingDevice} />}
        <RouteLines3D segments={routeSegments} />
        <gridHelper position={scene?.target} args={[scene ? scene.extent * 2 : 20, 20, '#7890a8', '#c5d0da']} />
        <axesHelper args={[2]} />
        <ViewerCameraControls ref={controlsRef} onReady={onControlsReady} target={scene?.target} extent={scene?.extent}
          enabled={!draggingDevice} panMode={navigationMode === 'pan'} />
      </Canvas>
    </section>
  )
}
