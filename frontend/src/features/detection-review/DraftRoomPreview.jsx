import { useMemo, useRef, useState } from 'react'
import { Viewer3DCanvas } from '../viewer-3d/Viewer3DCanvas.jsx'
import { Viewer3DErrorBoundary } from '../viewer-3d/Viewer3DErrorBoundary.jsx'
import { buildDraftRoomScene } from './draftRoomScene.js'
import { Button } from '../../components/ui/button.jsx'
import { clampDevicePoint } from './devicePresentation.js'

export function DraftRoomPreview({ draft, layers, width, height, projectId, presentations, selected, onSelect, onUpdateSymbol, navigationMode }) {
  const controlsRef = useRef(null)
  const [ready, setReady] = useState(false)
  const [wallHeight, setWallHeight] = useState(3)
  const [longSideMeters, setLongSideMeters] = useState(40)
  const [showRoof, setShowRoof] = useState(false)
  const result = useMemo(() => {
    try {
      const scene = buildDraftRoomScene(draft, width, height, wallHeight * 10 / longSideMeters, presentations, { longSideMeters })
      return { scene: { ...scene, walls: layers?.walls === false ? [] : scene.walls,
        roofRooms: scene.rooms, rooms: layers?.rooms === false ? [] : scene.rooms, symbols: layers?.symbols === false ? [] : scene.symbols } }
    }
    catch (error) { return { error: error.message } }
  }, [draft, layers, width, height, wallHeight, longSideMeters, presentations])
  return <section aria-label="Unfinished room preview">
    <p className="demo-preview-notice">Draft preview · Ceiling lights sit at wall-top height. Equipment uses typical sizes; preview dimensions below do not change saved measurements.</p>
    <div className="studio-3d-hud" role="group" aria-label="3D camera views">
      <Button variant="outline" size="sm" disabled={!ready} onClick={() => controlsRef.current?.reset()}>Perspective</Button>
      <Button variant="outline" size="sm" disabled={!ready} onClick={() => controlsRef.current?.top()}>Top view</Button>
      <Button variant="outline" size="sm" disabled={!ready} onClick={() => controlsRef.current?.front()}>Front view</Button>
      <Button variant="ghost" size="sm" disabled={!ready} onClick={() => controlsRef.current?.reset()}>Reset view</Button>
      <Button variant="outline" size="sm" aria-pressed={showRoof} onClick={() => setShowRoof((value) => !value)}>{showRoof ? 'Hide roof' : 'Show roof'}</Button>
    </div>
    <details className="studio-preview-dimensions"><summary>Preview dimensions · {longSideMeters} m plan length · {wallHeight} m walls</summary>
      <label>Source page long side (m)<input type="number" min="5" max="500" step="1" value={longSideMeters} onChange={(event) => { const value = Number(event.target.value); if (value >= 5 && value <= 500) setLongSideMeters(value) }} /></label>
      <label>Wall height (m)<input type="number" min="2" max="6" step="0.1" value={wallHeight} onChange={(event) => { const value = Number(event.target.value); if (value >= 2 && value <= 6) setWallHeight(value) }} /></label>
      <p>Adjust the page length to match your drawing. Defaults: 600 × 1200 mm troffers, 180 mm walls, outlets at 0.3 m, switches at 1.2 m. Roof cover is illustrative, not a structural roof model.</p>
    </details>
    {result.error ? <p role="alert">{result.error}</p> : result.scene.rooms.length === 0 && result.scene.walls.length === 0 && result.scene.symbols.length === 0 ? <p>No wall, room or device geometry yet. Return to 2D to add proposals.</p> :
      <Viewer3DErrorBoundary projectId={projectId} title="Draft 3D preview unavailable">
        <Viewer3DCanvas scene={result.scene} showRoof={showRoof} controlsRef={controlsRef} onControlsReady={setReady}
          selectedSymbolId={selected?.kind === 'symbol' ? selected.id : null} navigationMode={navigationMode}
          onSelectSymbol={(id) => onSelect?.({ kind: 'symbol', id })}
          onMoveSymbol={navigationMode === 'pan' ? undefined : (id, point) => {
            const symbol = draft.symbols.find((item) => item.id === id)
            const center = clampDevicePoint({ x: point.x / result.scene.sourceScale, y: point.y / result.scene.sourceScale }, width, height)
            if (symbol && center) onUpdateSymbol?.({ ...symbol, center })
          }} />
      </Viewer3DErrorBoundary>}
    {result.scene?.invalidSymbolCount > 0 && <p role="alert">{result.scene.invalidSymbolCount} invalid device positions omitted. Correct them in the inspector.</p>}
    <p>Drag a device to move it on the plan · drag empty space to orbit · right-drag to pan · scroll to zoom. Both views edit the same draft.</p>
  </section>
}
