import { useEffect, useRef, useState } from 'react'

import { fetchCurrentLayout, LayoutApiError, saveCurrentLayout } from '../../api/layouts.js'
import { fetchReviewImage } from '../../api/reviewImages.js'
import { canonicalGeometriesEqual, moveCanonicalSymbol } from '../../geometry/canonicalGeometry.js'
import { getProjectHref } from '../../routes/projectRoutes.js'
import { CanonicalLayoutCanvas } from './CanonicalLayoutCanvas.jsx'
import { LayoutLayerControls } from './LayoutLayerControls.jsx'
import { LayoutSymbolEditor } from './LayoutSymbolEditor.jsx'
import { resolveBlueprintProvenance } from './layoutCanvasGeometry.js'
import { LAYOUT_LAYER_LABELS } from './layoutLayers.js'
import './layoutEditor.css'

const INITIAL_VISIBILITY = Object.freeze({
  blueprint: true, walls: true, rooms: true, symbols: true, routes: true,
})
const INITIAL_SAVE_STATE = Object.freeze({ status: 'idle', error: null, idempotencyKey: null })

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

function saveFailure(error) {
  if (!(error instanceof LayoutApiError)) {
    return { status: 'uncertain', message: 'The save result is uncertain. Check the server before retrying.' }
  }
  if (error.status === 403) return { status: 'access-lost', message: 'Your edit access changed. This layout is now read-only.' }
  if (error.status === 404) return { status: 'idle', message: 'This layout context is no longer available. Your unsaved changes were not saved.' }
  if (error.status === 422) return { status: 'idle', message: 'The canonical geometry is invalid and was not saved.' }
  if (error.status === 409) {
    return {
      status: 'conflict',
      message: error.code === 'IDEMPOTENCY_KEY_CONFLICT'
        ? 'This save identity conflicts with an earlier request. Reload before editing again.'
        : 'A newer layout version exists. Reload before editing again.',
    }
  }
  if (error.status === 0 || error.status === 503) {
    return { status: 'uncertain', message: 'The save result is uncertain. Check the server before retrying.' }
  }
  return { status: 'idle', message: 'The layout changes could not be saved. Please try again.' }
}

export function LayoutEditorPage({ projectId, projectFloorId, session }) {
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState({
    status: 'loading', serverLayout: null, draft: null,
    image: null, blueprintWarning: null, error: null,
  })
  const [visibility, setVisibility] = useState({ ...INITIAL_VISIBILITY })
  const [selectedSymbolId, setSelectedSymbolId] = useState(null)
  const [saveState, setSaveState] = useState(INITIAL_SAVE_STATE)
  const [announcement, setAnnouncement] = useState('All canonical layout layers are visible.')
  const saveControllerRef = useRef(null)

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    let objectUrl = null
    saveControllerRef.current?.abort()

    async function load() {
      setState({ status: 'loading', serverLayout: null, draft: null, image: null, blueprintWarning: null, error: null })
      try {
        const serverLayout = await fetchCurrentLayout(projectId, projectFloorId, { signal: controller.signal })
        let image = null
        let blueprintWarning = null
        const provenance = resolveBlueprintProvenance(serverLayout.geometry)
        if (!provenance) {
          blueprintWarning = 'The aligned blueprint is unavailable because this snapshot has missing or mixed processing provenance.'
        } else {
          try {
            const blob = await fetchReviewImage(
              provenance.floorPlanId, provenance.processingJobId, { signal: controller.signal },
            )
            objectUrl = URL.createObjectURL(blob)
            image = await decodeImage(objectUrl)
            const coordinateSystem = serverLayout.geometry.coordinate_system
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
        if (active) {
          setState({ status: 'ready', serverLayout, draft: serverLayout.geometry, image, blueprintWarning, error: null })
        }
      } catch (error) {
        if (!active || error.name === 'AbortError') return
        if (error instanceof LayoutApiError && error.status === 401) {
          window.location.replace('#/signin?reason=session-expired')
          return
        }
        setState({ status: 'error', serverLayout: null, draft: null, image: null, blueprintWarning: null, error: pageError(error) })
      }
    }

    load()
    return () => {
      active = false
      controller.abort()
      saveControllerRef.current?.abort()
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

  function retryLoad() {
    setSelectedSymbolId(null)
    setSaveState(INITIAL_SAVE_STATE)
    setAttempt((value) => value + 1)
  }

  function selectSymbol(symbolId) {
    setSelectedSymbolId(symbolId)
    setAnnouncement(`Selected canonical symbol ${symbolId}.`)
  }

  function replaceDraft(nextGeometry) {
    setState((current) => current.status === 'ready' ? { ...current, draft: nextGeometry } : current)
    setSaveState(INITIAL_SAVE_STATE)
    setAnnouncement('Symbol position updated in the unsaved canonical layout.')
  }

  function moveSymbol(symbolId, position) {
    if (state.status !== 'ready') return
    try {
      replaceDraft(moveCanonicalSymbol(state.draft, symbolId, position))
    } catch {
      setSaveState({ ...INITIAL_SAVE_STATE, error: 'The symbol position is invalid.' })
    }
  }

  function adoptSavedLayout(serverLayout, message) {
    setState((current) => ({ ...current, serverLayout, draft: serverLayout.geometry }))
    if (!serverLayout.geometry.symbols.some((symbol) => symbol.id === selectedSymbolId)) setSelectedSymbolId(null)
    setSaveState(INITIAL_SAVE_STATE)
    setAnnouncement(message)
  }

  async function reconcileUncertainSave() {
    if (state.status !== 'ready' || saveState.status !== 'uncertain') return
    const controller = new AbortController()
    saveControllerRef.current = controller
    setSaveState((current) => ({ ...current, status: 'reconciling', error: null }))
    try {
      const current = await fetchCurrentLayout(projectId, projectFloorId, { signal: controller.signal })
      if (canonicalGeometriesEqual(current.geometry, state.draft)) {
        adoptSavedLayout(current, `Layout version ${current.version_number} is saved.`)
      } else if (current.id === state.serverLayout.id
        && current.version_number === state.serverLayout.version_number
        && canonicalGeometriesEqual(current.geometry, state.serverLayout.geometry)) {
        setSaveState((previous) => ({ ...previous, status: 'idle', error: 'The server still has the previous version. Select Save layout again to retry.' }))
        setAnnouncement('The previous server version is unchanged. A controlled save retry is available.')
      } else {
        setSaveState((previous) => ({ ...previous, status: 'conflict', error: 'A different layout version now exists. Discard these changes or reload before editing again.' }))
        setAnnouncement('A conflicting server layout was found. No overwrite was attempted.')
      }
    } catch (error) {
      if (error.name === 'AbortError') return
      if (error instanceof LayoutApiError && error.status === 401) {
        window.location.replace('#/signin?reason=session-expired')
        return
      }
      setSaveState((previous) => ({ ...previous, status: 'uncertain', error: 'The current server layout could not be checked. Your unsaved draft is retained.' }))
    } finally {
      if (saveControllerRef.current === controller) saveControllerRef.current = null
    }
  }

  async function saveLayout() {
    if (saveState.status === 'uncertain') {
      await reconcileUncertainSave()
      return
    }
    if (state.status !== 'ready' || saveState.status !== 'idle') return
    if (canonicalGeometriesEqual(state.serverLayout.geometry, state.draft)) return
    const controller = new AbortController()
    const idempotencyKey = saveState.idempotencyKey ?? globalThis.crypto.randomUUID()
    saveControllerRef.current = controller
    setSaveState({ status: 'saving', error: null, idempotencyKey })
    try {
      const saved = await saveCurrentLayout(projectId, projectFloorId, state.draft, {
        signal: controller.signal,
        expectedVersionNumber: state.serverLayout.version_number,
        idempotencyKey,
      })
      adoptSavedLayout(saved, `Layout version ${saved.version_number} saved successfully.`)
    } catch (error) {
      if (error.name === 'AbortError') return
      if (error instanceof LayoutApiError && error.status === 401) {
        window.location.replace('#/signin?reason=session-expired')
        return
      }
      const failure = saveFailure(error)
      setSaveState({ status: failure.status, error: failure.message, idempotencyKey })
      setAnnouncement(failure.message)
    } finally {
      if (saveControllerRef.current === controller) saveControllerRef.current = null
    }
  }

  function cancelChanges() {
    if (state.status !== 'ready') return
    setState((current) => ({ ...current, draft: current.serverLayout.geometry }))
    setSaveState(INITIAL_SAVE_STATE)
    setAnnouncement('Unsaved symbol position changes were discarded.')
  }

  if (state.status === 'loading') return <div className="layout-page-state" role="status">Loading the current canonical layout…</div>

  if (state.status === 'error') {
    return (
      <section className="layout-page-state layout-page-error" aria-labelledby="layout-error-title">
        <h1 id="layout-error-title">2D layout unavailable</h1>
        <p role="alert">{state.error.message}</p>
        {state.error.kind === 'temporary' && <button className="btn btn-dark" type="button" onClick={retryLoad}>Retry</button>}
        <a href={getProjectHref(projectId)}>Back to project</a>
      </section>
    )
  }

  const { serverLayout, draft: geometry } = state
  const dirty = !canonicalGeometriesEqual(serverLayout.geometry, geometry)
  const roleAllowsEditing = session?.user?.role === 'DESIGNER'
  const canEdit = roleAllowsEditing && saveState.status !== 'access-lost'
  const busy = ['saving', 'reconciling'].includes(saveState.status)
  const editBlocked = busy || ['uncertain', 'conflict'].includes(saveState.status)
  const saveDisabled = !canEdit || !dirty || busy || saveState.status === 'conflict'
  const counts = {
    walls: geometry.walls.length, rooms: geometry.rooms.length,
    symbols: geometry.symbols.length, routes: geometry.routes.length,
  }

  return (
    <article className="layout-editor-page" aria-labelledby="layout-page-title">
      <a className="layout-back-link" href={getProjectHref(projectId)}>← Back to project</a>
      <header className="layout-page-header">
        <div>
          <span className="project-kicker mono">CURRENT CANONICAL LAYOUT · VERSION {serverLayout.version_number}</span>
          <h1 id="layout-page-title">{geometry.floor.name} 2D layout</h1>
          <p>Canonical symbol positions can be reviewed and saved for planning.</p>
        </div>
        {!canEdit && <p className="layout-readonly-note" role="note">{session?.user?.role === 'ADMIN' ? 'Admin read-only view' : 'Read-only view'}</p>}
      </header>

      <dl className="layout-metadata">
        <div><dt>Project ID</dt><dd>{serverLayout.project_id}</dd></div>
        <div><dt>Floor ID</dt><dd>{serverLayout.project_floor_id}</dd></div>
        <div><dt>Elevation</dt><dd>{geometry.floor.elevation_meters} m</dd></div>
        <div><dt>Source floor-plan ID</dt><dd>{serverLayout.floor_plan_id}</dd></div>
      </dl>

      {state.blueprintWarning && <p className="layout-blueprint-warning" role="status">{state.blueprintWarning}</p>}

      <div className={`layout-save-bar ${dirty ? 'is-dirty' : 'is-saved'}`}>
        <p><strong>{dirty ? 'Unsaved position changes' : 'All position changes saved'}</strong><br />Server layout version {serverLayout.version_number}</p>
        {(canEdit || dirty) && (
          <div className="layout-save-actions">
            {canEdit && (
              <button className="btn btn-dark" type="button" disabled={saveDisabled} onClick={saveLayout}>
                {saveState.status === 'saving' ? 'Saving…' : saveState.status === 'reconciling' ? 'Checking server…' : saveState.status === 'uncertain' ? 'Check server before retry' : 'Save layout'}
              </button>
            )}
            <button className="btn btn-ghost" type="button" disabled={!dirty || busy} onClick={cancelChanges}>Cancel changes</button>
          </div>
        )}
      </div>
      {saveState.error && <p className="layout-save-error" role="alert">{saveState.error}</p>}

      <LayoutLayerControls visibility={visibility} onChange={toggleLayer} />
      <p className="sr-only" aria-live="polite">{announcement}</p>

      <CanonicalLayoutCanvas
        geometry={geometry}
        blueprintImage={state.image}
        visibility={visibility}
        selectedSymbolId={selectedSymbolId}
        canEdit={canEdit}
        editDisabled={editBlocked}
        onSelectSymbol={selectSymbol}
        onMoveSymbol={moveSymbol}
      />

      <LayoutSymbolEditor
        geometry={geometry}
        selectedSymbolId={selectedSymbolId}
        canEdit={canEdit}
        disabled={editBlocked}
        onSelectSymbol={selectSymbol}
        onGeometryChange={replaceDraft}
      />

      <section className="layout-accessible-summary" aria-labelledby="layout-summary-title">
        <h2 id="layout-summary-title">Layout summary</h2>
        <p>{geometry.floor.name}, layout version {serverLayout.version_number}. {dirty ? 'Unsaved symbol positions are shown.' : 'Saved symbol positions are shown.'}</p>
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
