import { useMemo, useRef, useState } from 'react'
import { Viewer3DCanvas } from '../viewer-3d/Viewer3DCanvas.jsx'
import { Viewer3DErrorBoundary } from '../viewer-3d/Viewer3DErrorBoundary.jsx'
import { buildDraftRoomScene } from './draftRoomScene.js'
import { Button } from '../../components/ui/button.jsx'
import { clampDevicePoint } from './devicePresentation.js'
import { findWireEndpointSnap, findWireEndpointTargets } from './wirePathSnap.js'
import { useUserPreferences } from '../settings/useUserPreferences.js'

export function DraftRoomPreview({ draft, layers, width, height, projectId, presentations, selected, onSelect, onUpdateSymbol, onMoveWirePoint, navigationMode, routingContext }) {
  const { preferences } = useUserPreferences()
  const controlsRef = useRef(null)
  const [ready, setReady] = useState(false)
  const [wallHeight, setWallHeight] = useState(3)
  const [longSideMeters, setLongSideMeters] = useState(40)
  const [showRoof, setShowRoof] = useState(false)
  const confirmedScale=routingContext?.pixels_per_meter
  const measuredLength=Number.isFinite(confirmedScale)&&confirmedScale>0 ? Math.max(width,height)/confirmedScale : null
  const result = useMemo(() => {
    try {
      const scene = buildDraftRoomScene(draft, width, height, wallHeight * 10 / (measuredLength??longSideMeters), presentations,
        { longSideMeters, pixelsPerMeter:confirmedScale, floorElevationMeters:routingContext?.floor_elevation_meters,
          planningMountingHeights:{switch:1.2,outlet:.45} })
      return { scene: { ...scene, walls: layers?.walls === false ? [] : scene.walls,
        roofRooms: scene.rooms, rooms: layers?.rooms === false ? [] : scene.rooms, symbols: layers?.symbols === false ? [] : scene.symbols,
        draftWires: layers?.wirings === false ? [] : scene.draftWires } }
    }
    catch (error) { return { error: error.message } }
  }, [draft, layers, width, height, wallHeight, longSideMeters, presentations, routingContext,measuredLength,confirmedScale])
  const connectedDevices = new Set(result.scene?.draftWires.flatMap(w => w.deviceIds) || [])
  const unmeasuredDevices = new Set(result.scene?.draftWires.flatMap(w => w.unmeasuredDeviceIds) || [])
  return <section aria-label="Unfinished room preview">
    <p className="demo-preview-notice">Draft 3D · {connectedDevices.size} connected devices. Unset dimensions use illustrative heights; only saved elevations contribute drops/rises to BOM.</p>
    {unmeasuredDevices.size>0 && <p role="note">{unmeasuredDevices.size} connections use planning presets, not measured drops/rises. Switches: 1.2 m above each floor; outlets: 0.45 m accessibility-oriented assumption. Saved heights override these; preset-only drops are excluded from measured BOM.</p>}
    <div className="studio-3d-hud" role="group" aria-label="3D camera views">
      <Button variant="outline" size="sm" disabled={!ready} onClick={() => controlsRef.current?.reset()}>Perspective</Button>
      <Button variant="outline" size="sm" disabled={!ready} onClick={() => controlsRef.current?.top()}>Top view</Button>
      <Button variant="outline" size="sm" disabled={!ready} onClick={() => controlsRef.current?.front()}>Front view</Button>
      <Button variant="ghost" size="sm" disabled={!ready} onClick={() => controlsRef.current?.reset()}>Reset view</Button>
      <Button variant="outline" size="sm" aria-pressed={showRoof} onClick={() => setShowRoof((value) => !value)}>{showRoof ? 'Hide roof' : 'Show roof'}</Button>
    </div>
    <details className="studio-preview-dimensions"><summary>Preview dimensions · {measuredLength??longSideMeters} m plan length · {wallHeight} m default walls</summary>
      <label>Source page long side (m)<input type="number" disabled={measuredLength!=null} min="5" max="500" step="1" value={measuredLength??longSideMeters} onChange={(event) => { const value = Number(event.target.value); if (value >= 5 && value <= 500) setLongSideMeters(value) }} /></label>
      {measuredLength!=null&&<p>Confirmed page scale is active. Per-wall dimensions override illustrative defaults.</p>}
      <label>Wall height (m)<input type="number" min="2" max="6" step="0.1" value={wallHeight} onChange={(event) => { const value = Number(event.target.value); if (value >= 2 && value <= 6) setWallHeight(value) }} /></label>
      <p>Adjust the page length to match your drawing. Defaults: 600 × 1200 mm troffers, 180 mm walls. Mounting presets use each floor's finished-floor reference, not an assumed floor-to-floor height. Roof cover is illustrative.</p>
    </details>
    {result.error ? <p role="alert">{result.error}</p> : result.scene.rooms.length === 0 && result.scene.walls.length === 0 && result.scene.symbols.length === 0 && result.scene.draftWires.length === 0 ? <p>No geometry yet. Return to 2D to add walls, devices or wiring.</p> :
      <Viewer3DErrorBoundary projectId={projectId} title="Draft 3D preview unavailable">
        <Viewer3DCanvas scene={result.scene} showRoof={showRoof} controlsRef={controlsRef} onControlsReady={setReady}
          selectedWireId={selected?.kind === 'wiring' ? selected.id : null}
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
          onMoveSymbol={navigationMode === 'pan' ? undefined : (id, point) => {
            const symbol = draft.symbols.find((item) => item.id === id)
            const center = clampDevicePoint({ x: point.x / result.scene.sourceScale, y: point.y / result.scene.sourceScale }, width, height)
            if (symbol && center) onUpdateSymbol?.({ ...symbol, center })
          }} />
      </Viewer3DErrorBoundary>}
    {result.scene?.invalidSymbolCount > 0 && <p role="alert">{result.scene.invalidSymbolCount} invalid device positions omitted. Correct them in the inspector.</p>}
    {result.scene?.invalidWiringCount > 0 && <p role="alert">{result.scene.invalidWiringCount} invalid wiring traces omitted. Correct their points in the inspector.</p>}
    <p>Click wiring, then drag a blue endpoint toward a device. Green means release to connect. Drag away to detach. Both views edit the same draft.</p>
  </section>
}
