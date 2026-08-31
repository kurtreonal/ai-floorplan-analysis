import { useEffect, useState } from 'react'

import { fetchCurrentLayout, LayoutApiError } from '../../api/layouts.js'
import { fetchReviewImage } from '../../api/reviewImages.js'
import { getProjectHref } from '../../routes/projectRoutes.js'
import { CanonicalLayoutCanvas } from './CanonicalLayoutCanvas.jsx'
import { LayoutLayerControls } from './LayoutLayerControls.jsx'
import { resolveBlueprintProvenance } from './layoutCanvasGeometry.js'
import { LAYOUT_LAYER_LABELS } from './layoutLayers.js'
import './layoutEditor.css'

const INITIAL_VISIBILITY = Object.freeze({
  blueprint: true, walls: true, rooms: true, symbols: true, routes: true,
})

function decodeImage(url) {
  return new Promise((resolve, reject) => {
    const image = new window.Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('decode failed'))
    image.src = url
  })
}

function pageError(error) {
  if (error instanceof LayoutApiError) {
    if (error.status === 403 || error.status === 404) return { kind: 'missing', message: 'No current layout is available for this project floor.' }
    if (error.status === 422) return { kind: 'invalid', message: 'The 2D layout address or data is invalid.' }
  }
  return { kind: 'temporary', message: 'The current 2D layout could not be loaded safely. Please try again.' }
}

export function LayoutEditorPage({ projectId, projectFloorId, session }) {
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState({ status: 'loading', layout: null, image: null, blueprintWarning: null, error: null })
  const [visibility, setVisibility] = useState({ ...INITIAL_VISIBILITY })
  const [announcement, setAnnouncement] = useState('All canonical layout layers are visible.')

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    let objectUrl = null

    async function load() {
      setState({ status: 'loading', layout: null, image: null, blueprintWarning: null, error: null })
      try {
        const layout = await fetchCurrentLayout(projectId, projectFloorId, { signal: controller.signal })
        let image = null
        let blueprintWarning = null
        const provenance = resolveBlueprintProvenance(layout.geometry)
        if (!provenance) {
          blueprintWarning = 'The aligned blueprint is unavailable because this snapshot has missing or mixed processing provenance.'
        } else {
          try {
            const blob = await fetchReviewImage(
              provenance.floorPlanId,
              provenance.processingJobId,
              { signal: controller.signal },
            )
            objectUrl = URL.createObjectURL(blob)
            image = await decodeImage(objectUrl)
            const coordinateSystem = layout.geometry.coordinate_system
            if (image.naturalWidth !== coordinateSystem.image_width_pixels
              || image.naturalHeight !== coordinateSystem.image_height_pixels) {
              image = null
              blueprintWarning = 'The aligned blueprint dimensions do not match this canonical snapshot.'
            }
          } catch (error) {
            if (error.name === 'AbortError') throw error
            image = null
            blueprintWarning = 'The aligned blueprint could not be loaded safely. Canonical geometry remains available.'
          }
        }
        if (active) setState({ status: 'ready', layout, image, blueprintWarning, error: null })
      } catch (error) {
        if (!active || error.name === 'AbortError') return
        if (error instanceof LayoutApiError && error.status === 401) {
          window.location.replace('#/signin?reason=session-expired')
          return
        }
        setState({ status: 'error', layout: null, image: null, blueprintWarning: null, error: pageError(error) })
      }
    }

    load()
    return () => {
      active = false
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [attempt, projectFloorId, projectId])

  function toggleLayer(layer) {
    setVisibility((current) => {
      const next = { ...current, [layer]: !current[layer] }
      setAnnouncement(`${LAYOUT_LAYER_LABELS[layer]} layer ${next[layer] ? 'visible' : 'hidden'}.`)
      return next
    })
  }

  if (state.status === 'loading') {
    return <div className="layout-page-state" role="status">Loading the current canonical layout…</div>
  }

  if (state.status === 'error') {
    return (
      <section className="layout-page-state layout-page-error" aria-labelledby="layout-error-title">
        <h1 id="layout-error-title">2D layout unavailable</h1>
        <p role="alert">{state.error.message}</p>
        {state.error.kind === 'temporary' && (
          <button className="btn btn-dark" type="button" onClick={() => setAttempt((value) => value + 1)}>Retry</button>
        )}
        <a href={getProjectHref(projectId)}>Back to project</a>
      </section>
    )
  }

  const { layout } = state
  const { geometry } = layout
  const counts = {
    walls: geometry.walls.length,
    rooms: geometry.rooms.length,
    symbols: geometry.symbols.length,
    routes: geometry.routes.length,
  }

  return (
    <article className="layout-editor-page" aria-labelledby="layout-page-title">
      <a className="layout-back-link" href={getProjectHref(projectId)}>← Back to project</a>
      <header className="layout-page-header">
        <div>
          <span className="project-kicker mono">CURRENT CANONICAL LAYOUT · VERSION {layout.version_number}</span>
          <h1 id="layout-page-title">{geometry.floor.name} 2D layout</h1>
          <p>Read-only canonical geometry for planning and review.</p>
        </div>
        {session?.user?.role === 'ADMIN' && <p className="layout-readonly-note" role="note">Admin read-only view</p>}
      </header>

      <dl className="layout-metadata">
        <div><dt>Project ID</dt><dd>{layout.project_id}</dd></div>
        <div><dt>Floor ID</dt><dd>{layout.project_floor_id}</dd></div>
        <div><dt>Elevation</dt><dd>{geometry.floor.elevation_meters} m</dd></div>
        <div><dt>Source floor-plan ID</dt><dd>{layout.floor_plan_id}</dd></div>
      </dl>

      {state.blueprintWarning && <p className="layout-blueprint-warning" role="status">{state.blueprintWarning}</p>}

      <LayoutLayerControls visibility={visibility} onChange={toggleLayer} />
      <p className="sr-only" aria-live="polite">{announcement}</p>

      <CanonicalLayoutCanvas geometry={geometry} blueprintImage={state.image} visibility={visibility} />

      <section className="layout-accessible-summary" aria-labelledby="layout-summary-title">
        <h2 id="layout-summary-title">Layout summary</h2>
        <p>{geometry.floor.name}, layout version {layout.version_number}.</p>
        <ul>
          <li>{counts.walls} walls</li><li>{counts.rooms} rooms</li>
          <li>{counts.symbols} symbols</li><li>{counts.routes} route previews</li>
          <li>Blueprint {state.image ? 'available' : 'unavailable'}</li>
        </ul>
        <p>{Object.entries(visibility).map(([key, visible]) => `${LAYOUT_LAYER_LABELS[key]} ${visible ? 'visible' : 'hidden'}`).join(' · ')}</p>
      </section>

      <div className="layout-symbol-legend" aria-label="Canonical symbol provenance legend">
        <span><i className="is-detected" aria-hidden="true" />D · Confirmed AI detection</span>
        <span><i className="is-manual" aria-hidden="true" />M · Manually added symbol</span>
        <span><i className="is-route" aria-hidden="true" />Dashed · Stored route preview</span>
      </div>
    </article>
  )
}
