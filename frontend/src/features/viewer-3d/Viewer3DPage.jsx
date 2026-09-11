import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchCurrentLayout } from '../../api/layouts.js'
import { buildCanonicalScene } from './canonicalScene.js'

import { getProjectHref } from '../../routes/projectRoutes.js'
import { Viewer3DCanvas } from './Viewer3DCanvas.jsx'
import { Viewer3DErrorBoundary } from './Viewer3DErrorBoundary.jsx'
import './viewer3d.css'


export default function Viewer3DPage({ projectId, projectFloorId }) {
  const controlsRef = useRef(null)
  const [controlsReady, setControlsReady] = useState(false)
  const [canvasAttempt, setCanvasAttempt] = useState(0)
  const [layoutState, setLayoutState] = useState({ status: 'loading' })
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

  return (
    <article className="viewer-3d-page" aria-labelledby="viewer-3d-title">
      <a className="viewer-3d-back-link" href={getProjectHref(projectId)}>← Back to project</a>
      <header className="viewer-3d-header">
        <div>
          <span className="project-kicker mono">SAVED 3D LAYOUT · FLOOR #{projectFloorId}</span>
          <h1 id="viewer-3d-title">3D planning workspace</h1>
          <p>Room surfaces, walls and symbol markers from the shared saved layout.</p>
        </div>
        <button
          className="btn btn-dark"
          type="button"
          disabled={!controlsReady}
          onClick={resetCamera}
        >
          Reset view
        </button>
        <button className="btn btn-dark" type="button" disabled={!controlsReady} onClick={() => controlsRef.current?.top()}>Top view</button>
        <button className="btn btn-dark" type="button" disabled={!controlsReady} onClick={resetCamera}>Perspective view</button>
      </header>

      <p className="viewer-3d-scope-note" role="note">
        Symbol markers show floor positions; they do not specify mounting height. Reload the layout after saving 2D changes.
      </p>
      <p className="sr-only" aria-live="polite">{announcement}</p>

      {layoutState.status === 'loading' && <p role="status">Loading saved layout…</p>}
      {layoutState.status === 'error' && <p role="alert">{layoutState.message}</p>}
      {layoutState.status === 'ready' && <p>Saved version {layoutState.layout.version_number}: {layoutState.scene.rooms.length} rooms, {layoutState.scene.walls.length} verified walls, {layoutState.scene.symbols.length} symbols.</p>}
      {layoutState.status === 'ready' && <Viewer3DErrorBoundary
        key={canvasAttempt}
        projectId={projectId}
        title="3D canvas unavailable"
      >
        <Viewer3DCanvas scene={layoutState.scene} controlsRef={controlsRef} onControlsReady={handleControlsReady} />
      </Viewer3DErrorBoundary>}

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
          onClick={() => setCanvasAttempt((attempt) => attempt + 1)}
        >
          Restart 3D canvas
        </button>
      </section>
    </article>
  )
}
