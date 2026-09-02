import { useCallback, useRef, useState } from 'react'

import { getProjectHref } from '../../routes/projectRoutes.js'
import { Viewer3DCanvas } from './Viewer3DCanvas.jsx'
import { Viewer3DErrorBoundary } from './Viewer3DErrorBoundary.jsx'
import './viewer3d.css'


export default function Viewer3DPage({ projectId, projectFloorId }) {
  const controlsRef = useRef(null)
  const [controlsReady, setControlsReady] = useState(false)
  const [canvasAttempt, setCanvasAttempt] = useState(0)
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
          <span className="project-kicker mono">3D VIEWER FOUNDATION · FLOOR #{projectFloorId}</span>
          <h1 id="viewer-3d-title">3D planning workspace</h1>
          <p>Orbit, pan, and zoom around the empty reference scene.</p>
        </div>
        <button
          className="btn btn-dark"
          type="button"
          disabled={!controlsReady}
          onClick={resetCamera}
        >
          Reset view
        </button>
      </header>

      <p className="viewer-3d-scope-note" role="note">
        Floor-plan geometry is intentionally not loaded yet. Canonical 2D-to-3D mapping begins in L2.
      </p>
      <p className="sr-only" aria-live="polite">{announcement}</p>

      <Viewer3DErrorBoundary
        key={canvasAttempt}
        projectId={projectId}
        title="3D canvas unavailable"
      >
        <Viewer3DCanvas controlsRef={controlsRef} onControlsReady={handleControlsReady} />
      </Viewer3DErrorBoundary>

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
