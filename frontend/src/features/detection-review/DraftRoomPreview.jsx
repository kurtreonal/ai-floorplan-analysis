import { useMemo, useRef, useState } from 'react'
import { Viewer3DCanvas } from '../viewer-3d/Viewer3DCanvas.jsx'
import { Viewer3DErrorBoundary } from '../viewer-3d/Viewer3DErrorBoundary.jsx'
import { buildDraftRoomScene } from './draftRoomScene.js'

export function DraftRoomPreview({ draft, width, height, projectId }) {
  const controlsRef = useRef(null)
  const [ready, setReady] = useState(false)
  const [heightRatio, setHeightRatio] = useState(0.8)
  const result = useMemo(() => {
    try { return { scene: buildDraftRoomScene(draft, width, height, heightRatio) } }
    catch (error) { return { error: error.message } }
  }, [draft, width, height, heightRatio])
  return <section aria-label="Unfinished room preview">
    <p className="demo-preview-notice">DRAFT · Relative proportions only, not meters. Raised edges illustrate room boundaries, not detected walls or door openings. No approval or saved layout is created.</p>
    <div className="demo-add-actions">
      <button type="button" disabled={!ready} onClick={() => controlsRef.current?.reset()}>Reset view</button>
      <button type="button" disabled={!ready} onClick={() => controlsRef.current?.top()}>Top view</button>
      <label>Illustrative boundary height<input type="range" min="0" max="2" step="0.1" value={heightRatio} onChange={(event) => setHeightRatio(Number(event.target.value))} /></label>
    </div>
    {result.error ? <p role="alert">{result.error}</p> : result.scene.rooms.length === 0 ? <p>No room boundaries yet. Return to 2D and add a missing room to preview it here.</p> :
      <Viewer3DErrorBoundary projectId={projectId} title="Draft 3D preview unavailable">
        <Viewer3DCanvas scene={result.scene} controlsRef={controlsRef} onControlsReady={setReady} />
      </Viewer3DErrorBoundary>}
    <p>Drag to orbit · right-drag to pan · scroll to zoom. Return to 2D to correct the same room shapes.</p>
  </section>
}
