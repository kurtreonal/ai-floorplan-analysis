import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchCurrentLayout } from '../../api/layouts.js'
import { buildCanonicalScene } from './canonicalScene.js'
import { useSavedRoute } from '../routing/useSavedRoute.js'
import { projectRoute } from '../routing/routeProjection.js'
import { RoutingPanel } from '../routing/RoutingPanel.jsx'

import { getLayoutHref, getProjectHref } from '../../routes/projectRoutes.js'
import { Viewer3DCanvas } from './Viewer3DCanvas.jsx'
import { Viewer3DErrorBoundary } from './Viewer3DErrorBoundary.jsx'
import './viewer3d.css'
import { Button } from '../../components/ui/button.jsx'
import { Box, Layers3, RotateCcw, RefreshCw, Scan, Move3D } from 'lucide-react'


export default function Viewer3DPage({ projectId, projectFloorId }) {
  return <SavedViewer key={`${projectId}:${projectFloorId}`} projectId={projectId} projectFloorId={projectFloorId} />
}

function SavedViewer({ projectId, projectFloorId }) {
  const controlsRef = useRef(null)
  const [controlsReady, setControlsReady] = useState(false)
  const [canvasAttempt, setCanvasAttempt] = useState(0)
  const [selectedSymbolId, setSelectedSymbolId] = useState(null)
  const [showRoof, setShowRoof] = useState(false)
  const [layoutState, setLayoutState] = useState({ status: 'loading' })
  const [route, setRoute] = useSavedRoute(projectId, layoutState.layout?.id)
  useEffect(() => {
    const controller = new AbortController()
    fetchCurrentLayout(projectId, projectFloorId, { signal: controller.signal }).then((layout) => {
      if (!controller.signal.aborted) setLayoutState({ status: 'ready', layout, scene: buildCanonicalScene(layout.geometry) })
    }).catch((error) => {
      if (controller.signal.aborted) return
      setLayoutState({ status: 'error', message: error.status === 404
        ? 'No saved layout is available. Review and save the floor plan first.'
        : error.message === 'Approve wall height and thickness before opening metric 3D.'
          ? error.message : 'The saved layout could not be loaded. Check your session and access, then retry.' })
    })
    return () => controller.abort()
  }, [projectId, projectFloorId, canvasAttempt])
  const [announcement, setAnnouncement] = useState('3D camera controls are loading.')
  const handleControlsReady = useCallback((ready) => {
    setControlsReady(ready)
    if (ready) setAnnouncement('3D camera controls are ready.')
  }, [])

  function resetCamera() {
    controlsRef.current?.reset()
    setAnnouncement('3D camera reset to its initial view.')
  }

  function reloadLayout() {
    setLayoutState({ status: 'loading' })
    setControlsReady(false)
    setSelectedSymbolId(null)
    setCanvasAttempt((attempt) => attempt + 1)
  }

  return (
    <article className="viewer-3d-page" aria-labelledby="viewer-3d-title">
      <a className="viewer-3d-back-link" href={getProjectHref(projectId)}>← Back to project</a>
      <header className="viewer-3d-header">
        <div>
          <span className="project-kicker mono">SAVED 3D LAYOUT · FLOOR #{projectFloorId}</span>
          <h1 id="viewer-3d-title">3D planning workspace</h1>
          <p>Room surfaces, walls and named electrical devices from the shared saved layout.</p>
        </div>
      </header>

      <div className="studio-mode-bar"><Button variant="ghost" size="sm" asChild><a href={getLayoutHref(projectId, projectFloorId)}><Layers3 aria-hidden="true" />Compare saved 2D layout</a></Button><span className="studio-mode-active"><Box size={16} aria-hidden="true" />3D viewer</span><span className="mono">SAVED GEOMETRY · NO SEPARATE 3D MODEL</span></div>

      <p className="viewer-3d-scope-note" role="note">
        Devices use typical equipment sizes and mounting heights; ceiling lights follow wall tops. These are visual defaults, not equipment specifications. Reload after saving 2D changes.
      </p>
      <div className="studio-viewer-workbench">
      <aside className="studio-viewer-tools" aria-label="3D view tools"><span className="project-kicker mono">CAMERA</span><Button variant="outline" disabled={!controlsReady} onClick={resetCamera}><RotateCcw aria-hidden="true" />Reset view</Button><Button variant="outline" disabled={!controlsReady} onClick={() => controlsRef.current?.top()}><Scan aria-hidden="true" />Top view</Button><Button variant="outline" disabled={!controlsReady} onClick={resetCamera}><Move3D aria-hidden="true" />Perspective view</Button><Button variant="outline" disabled={layoutState.status === 'loading'} onClick={reloadLayout}><RefreshCw aria-hidden="true" />Reload saved layout</Button><p>Orbit, pan and zoom change your view—not saved coordinates.</p></aside>
      <div className="studio-viewer-scene">
      <Button variant="outline" size="sm" aria-pressed={showRoof} onClick={() => setShowRoof((value) => !value)}>{showRoof ? 'Hide roof' : 'Show roof'}</Button>
      {layoutState.status === 'loading' && <p role="status">Loading saved layout…</p>}
      {layoutState.status === 'error' && <p role="alert">{layoutState.message}</p>}
      {layoutState.status === 'ready' && <Viewer3DErrorBoundary
        key={canvasAttempt}
        projectId={projectId}
        title="3D canvas unavailable"
      >
        <Viewer3DCanvas scene={layoutState.scene} showRoof={showRoof} routeSegments={projectRoute(route, layoutState.layout)} controlsRef={controlsRef} onControlsReady={handleControlsReady}
          selectedSymbolId={selectedSymbolId} onSelectSymbol={setSelectedSymbolId} />
      </Viewer3DErrorBoundary>}
      </div>
      <aside className="studio-viewer-inspector"><span className="project-kicker mono">SAVED SNAPSHOT</span><h2>Geometry & provenance</h2>
      {layoutState.status === 'ready' && <>
        <label className="studio-field">Inspect device<select value={selectedSymbolId || ''} onChange={(event) => setSelectedSymbolId(event.target.value || null)}>
          <option value="">Select a device</option>{layoutState.scene.symbols.map((symbol) => <option key={symbol.id} value={symbol.id}>{symbol.classification.name} · {symbol.id}</option>)}
        </select></label>
        {layoutState.scene.symbols.filter((symbol) => symbol.id === selectedSymbolId).map((symbol) => <div key={symbol.id}>
          <h3>{symbol.classification.name}</h3><p>X {symbol.position[0]} m · Y {symbol.position[2]} m<br />{symbol.status} · {symbol.id}</p>
          <p>This saved snapshot is inspection-only. Use the review workspace for classification or removal, or saved 2D for supported position edits.</p>
        </div>)}
      </>}
      {layoutState.status === 'ready' && layoutState.layout.hasExtension && <p role="note">This view shows the canonical base geometry. Additional openings, panels and observed wiring remain in the saved review data and are not rendered here.</p>}
      {layoutState.status === 'ready' && <p>Source plane: {layoutState.scene.width} × {layoutState.scene.depth} m; floor elevation: {layoutState.scene.elevation} m. The rectangle represents the source image extent; room surfaces follow saved boundaries.</p>}
      {layoutState.status === 'ready' && layoutState.scene.omittedWallCount > 0 && <p role="note">{layoutState.scene.omittedWallCount} unverified or zero-length walls are omitted. Verified walls require stored height and thickness.</p>}
      <p className="sr-only" aria-live="polite">{announcement}</p>

      {layoutState.status === 'ready' && <p>Saved version {layoutState.layout.version_number}: {layoutState.scene.rooms.length} rooms, {layoutState.scene.walls.length} verified walls, {layoutState.scene.symbols.length} symbols.</p>}
      {layoutState.status === 'ready' && <details>
        <summary>Reviewed electrical symbols ({layoutState.scene.symbols.length})</summary>
        <ul>{layoutState.scene.symbols.map((symbol) => <li key={symbol.id}>
          {symbol.classification.name} (class {symbol.classification.id}) — {symbol.id}; {symbol.status === 'manually_added' ? 'manually added' : 'confirmed'}; x {symbol.position[0]} m, y {symbol.position[2]} m.
        </li>)}</ul>
      </details>}
      </aside>
      </div>
      {layoutState.status === 'ready' && <RoutingPanel key={layoutState.layout.id} layout={layoutState.layout} record={route} onSaved={setRoute} />}

      <section className="viewer-3d-help" aria-labelledby="viewer-3d-help-title">
        <h2 id="viewer-3d-help-title">Camera controls</h2>
        <ul>
          <li>Left-drag or use one finger to orbit around the origin.</li>
          <li>Right-drag or use a modified left-drag to pan.</li>
          <li>Use the wheel, middle button, or a two-finger gesture to zoom.</li>
        </ul>
        <button
          className="viewer-3d-retry"
          type="button"
          onClick={reloadLayout}
        >
          Restart 3D canvas
        </button>
      </section>
    </article>
  )
}
