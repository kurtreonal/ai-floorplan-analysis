import { useEffect, useRef, useState } from 'react'
import { orderNamed } from '../../utils/listOrder.js'
import { previewCircuit, saveCircuit } from '../../api/routing.js'
import { Button } from '../../components/ui/button.jsx'
import { CanonicalLayoutCanvas } from '../editor-2d/CanonicalLayoutCanvas.jsx'
import { projectRoute } from './routeProjection.js'
import { RoutingObstacles } from './RoutingObstacles.jsx'
import { normalizeRouteObstacles, obstacleRows, routingObstaclesFromRows } from './routeObstacles.js'

function routingFailure(failure) {
  const observedErrors = {
    OBSERVED_NETWORK_CIRCUIT_CONFLICT: 'Selected wiring is stored on another circuit. Review its assignment; circuits were not merged.',
    OBSERVED_NETWORK_REFERENCE_REQUIRED: 'Select existing reviewed observed routes from this saved layout.',
    OBSERVED_NETWORK_FLOOR_REVIEW_REQUIRED: 'The selected observed route crosses floors without a reviewed connector. Review it before reuse.',
    OBSERVED_NETWORK_PANEL_CONNECTION_REQUIRED: 'Selected routes must form a panel-connected network through shared endpoints. Crossings and nearby paths are not joined.',
    OBSERVED_NETWORK_OBSTACLE_CONFLICT: 'Selected observed wiring intersects a configured obstacle. Review the network or routing constraints.',
    OBSERVED_NETWORK_SERVICE_ELEVATION_REQUIRED: 'Selected observed wiring has no point at the entered service elevation. No heights were changed.',
  }
  if (observedErrors[failure.message]) return observedErrors[failure.message]
  if (failure.message === 'EXISTING_ROUTE_REVIEW_REQUIRED') return 'Existing saved wiring uses different assignments, constraints or a layout version. Review it before completion; no route was replaced.'
  if (failure.message === 'NO_NEW_ROUTE_TO_SAVE') return 'No eligible generated route to save. Existing connections remain unchanged.'
  return failure.message
}

export function CircuitPlanningPanel({ layout, record = null, onPreview, onSaved }) {
  const configuration = savedConfiguration(record, layout)
  // A saved snapshot arriving after mount restores once. Stable record identity
  // keeps ongoing form edits; changing the layout remounts and aborts old work.
  const snapshot = configuration ? `${record.id}:${record.version_number}` : 'new'
  return <CircuitForm key={`${layout.project_id}:${layout.project_floor_id}:${layout.id}:${layout.version_number}:${snapshot}`}
    layout={layout} record={record} initialConfiguration={configuration} onPreview={onPreview} onSaved={onSaved} />
}

function savedConfiguration(record, layout) {
  if (!record || record.stale || record.project_id !== layout.project_id
    || record.layout_versions?.[String(layout.project_floor_id)] !== layout.id
    || record.result?.status !== 'saved_planning') return null
  const configuration = record.configuration
  const observed = new Set((layout.extension?.route_details ?? []).filter(item => item.route_kind === 'observed').map(item => item.route_id))
  if ((configuration?.observed_route_assignments ?? []).some(item => item.floor_id !== layout.project_floor_id || !observed.has(item.route_id))) return null
  if (!['ceiling_service', 'underground'].includes(configuration?.installation_method) || configuration.floors?.length !== 1
    || !configuration.targets?.length || configuration.targets.length > 32
    || configuration.connectors?.length) return null
  try { normalizeRouteObstacles(configuration.obstacles, layout.project_floor_id) }
  catch { return null }
  if (configuration.installation_method === 'underground' && configuration.floor_passages_confirmed !== true) return null
  const floor = configuration.floors[0], panel = configuration.panel
  if (floor.floor_id !== layout.project_floor_id || floor.expected_layout_version !== layout.version_number
    || floor.offset_x !== 0 || floor.offset_y !== 0 || panel?.floor_id !== layout.project_floor_id
    || ![floor.service_elevation_meters, panel.x, panel.y, panel.elevation_meters, configuration.grid_step_meters].every(Number.isFinite)) return null
  const walls = new Set(layout.geometry.walls.filter((wall) => wall.status === 'verified').map((wall) => wall.id))
  const validWall = (id) => id == null || walls.has(id)
  const symbols = new Map(layout.geometry.symbols.map((symbol) => [symbol.id, symbol.position]))
  const ids = new Set()
  if (!validWall(panel.wall_id) || !configuration.targets.every((target) => {
    const position = symbols.get(target.symbol_id)
    if (ids.has(target.symbol_id)) return false
    ids.add(target.symbol_id)
    return target.floor_id === layout.project_floor_id && position && position.x === target.x && position.y === target.y
      && Number.isFinite(target.elevation_meters) && validWall(target.wall_id)
  })) return null
  return configuration
}

function CircuitForm({ layout, record, initialConfiguration, onPreview, onSaved }) {
  const [selected, setSelected] = useState(() => initialConfiguration?.targets.map((target) => target.symbol_id) ?? [])
  const [installation, setInstallation] = useState(initialConfiguration?.installation_method ?? '')
  const [missingOnly, setMissingOnly] = useState(initialConfiguration?.routing_mode !== 'shared_circuit')
  const [observedRoutes, setObservedRoutes] = useState(() => initialConfiguration?.observed_route_assignments?.map(item => item.route_id) ?? [])
  const [obstacles, setObstacles] = useState(() => obstacleRows(initialConfiguration?.obstacles, layout.project_floor_id))
  const [preview, setPreview] = useState(null)
  const [show2D, setShow2D] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [deferred, setDeferred] = useState([])
  const errorRef = useRef(null)
  const requestRef = useRef(null)
  const retryRef = useRef(null)
  const previewRef = useRef(null)
  const onPreviewRef = useRef(onPreview)
  useEffect(() => { onPreviewRef.current = onPreview }, [onPreview])
  useEffect(() => () => {
    requestRef.current?.abort()
    if (previewRef.current) onPreviewRef.current(null)
  }, [])
  useEffect(() => { if (error) errorRef.current?.focus() }, [error])

  function clearPreview() {
    const hadPreview = previewRef.current
    retryRef.current = null
    previewRef.current = null
    if (hadPreview) { setPreview(null); onPreview(null) }
  }

  function changeObstacles(rows) { setObstacles(rows); clearPreview() }

  async function save() {
    if (!preview || busy) return
    const configuration = retryRef.current ?? {
      ...preview.configuration, intent: 'save_planning_circuit',
      expected_route_version: record?.version_number ?? 0, request_id: globalThis.crypto.randomUUID(),
    }
    retryRef.current = configuration
    const controller = new AbortController()
    requestRef.current = controller
    setBusy(true); setError('')
    try {
      const saved = await saveCircuit(layout.project_id, configuration, { signal: controller.signal })
      if (controller.signal.aborted) return
      if (saved.stale || saved.layout_versions[String(layout.project_floor_id)] !== layout.id) throw new Error('Layout changed. Reload before using this saved circuit.')
      clearPreview(); onSaved(saved)
    } catch (failure) {
      if (!controller.signal.aborted) {
        setError(routingFailure(failure))
        if (failure.status && failure.status < 500) retryRef.current = null
      }
    } finally { if (!controller.signal.aborted) setBusy(false) }
  }

  async function submit(event) {
    event.preventDefault()
    if (!event.currentTarget.reportValidity()) return
    const form = new FormData(event.currentTarget)
    const number = (name) => {
      const value = form.get(name)
      if (value === null || value.trim() === '' || !Number.isFinite(Number(value))) throw new Error('Enter all selected elevations and panel coordinates.')
      return Number(value)
    }
    const wall = (name) => form.get(name) ? number(name) : null
    setError('')
    setDeferred([])
    clearPreview()
    let configuration
    try {
      if (!selected.length || selected.length > 32) throw new Error('Select between 1 and 32 devices for this circuit.')
      const missingHeights = missingOnly ? selected.filter((id) => !String(form.get(`height:${id}`) ?? '').trim()) : []
      setDeferred(missingHeights)
      const targets = layout.geometry.symbols.filter((symbol) => selected.includes(symbol.id) && !missingHeights.includes(symbol.id))
      if (!targets.length) throw new Error('No eligible devices: enter mounting elevations for at least one assigned device. The 2D draft remains available.')
      configuration = {
        routing_mode: missingOnly ? 'missing_devices' : 'shared_circuit',
        circuit_id: form.get('circuit').trim(), installation_method: form.get('installation'),
        floor_passages_confirmed: form.get('installation') === 'underground' && form.get('floorPassages') === 'on',
        floors: [{ floor_id: layout.project_floor_id, expected_layout_version: layout.version_number,
          service_elevation_meters: number('service'), offset_x: 0, offset_y: 0 }],
        panel: { floor_id: layout.project_floor_id, x: number('panelX'), y: number('panelY'),
          elevation_meters: number('panelHeight'), wall_id: wall('panelWall') },
        targets: targets.map((symbol) => ({
          floor_id: layout.project_floor_id, symbol_id: symbol.id, ...symbol.position,
          elevation_meters: number(`height:${symbol.id}`), wall_id: wall(`wall:${symbol.id}`),
        })),
        connectors: [], obstacles: routingObstaclesFromRows(obstacles, layout.project_floor_id),
        grid_step_meters: number('step'), alignment_confirmed: true, purpose: 'planning',
        observed_route_assignments: missingOnly ? observedRoutes.map(route_id => ({ floor_id: layout.project_floor_id, route_id })) : [],
      }
    } catch (failure) { setError(failure.message); return }
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    setBusy(true)
    try {
      const result = await previewCircuit(layout.project_id, configuration, { signal: controller.signal })
      if (controller.signal.aborted) return
      if (result.layout_versions[String(layout.project_floor_id)] !== layout.id) throw new Error('Layout changed. Reload before generating a preview.')
      setPreview(result)
      previewRef.current = result
      onPreview(result)
    } catch (failure) {
      if (!controller.signal.aborted) setError(routingFailure(failure))
    } finally { if (!controller.signal.aborted) setBusy(false) }
  }

  const walls = orderNamed(layout.geometry.walls.filter((wall) => wall.status === 'verified'), wall => wall.id)
  const observedIds = new Set((layout.extension?.route_details ?? []).filter(item => item.route_kind === 'observed').map(item => item.route_id))
  const observedChoices = (layout.geometry.routes ?? []).filter(route => observedIds.has(route.id))
  const savedTargets = new Map(initialConfiguration?.targets.map((target) => [target.symbol_id, target]) ?? [])
  const savedFields = initialConfiguration ? {
    panelX: initialConfiguration.panel.x, panelY: initialConfiguration.panel.y,
    panelHeight: initialConfiguration.panel.elevation_meters,
    service: initialConfiguration.floors[0].service_elevation_meters,
  } : {}
  const wallOptions = <><option value="">At service elevation; no wall attachment</option>{walls.map((wall) => <option key={wall.id} value={wall.id}>Wall {wall.id}</option>)}</>
  return <section aria-label="Shared circuit planning preview">
    <h2>Shared circuit preview</h2>
    {error && <p ref={errorRef} role="alert" tabIndex={-1}>{error}</p>}
    {record?.result.status === 'saved_planning' && <p role="status">Saved circuit {record.result.circuit_id}, route version {record.version_number}: {record.result.branches.length} devices; {record.result.total_meters.toFixed(3)} m unique path. {record.stale ? 'Layout changed; reload and recalculate.' : 'Entered planning elevations reload with this route; not electrical approval.'}</p>}
    {initialConfiguration && <p role="note">Saved circuit inputs restored. Confirm them before recalculating.</p>}
    {record?.result.status === 'saved_planning' && !initialConfiguration && <p role="note">Saved circuit inputs do not match this editable floor snapshot. Enter current inputs to recalculate; saved values have not been applied.</p>}
    <p>Assign saved devices to one circuit. Routes share a planning path; wall connections use your entered elevations and verified wall attachments.</p>
    <p>Existing drawing connections take priority. Completion never assigns a device to a nearby circuit. Missing scale or elevations require review; the 2D draft remains saveable.</p>
    {deferred.length > 0 && <p role="note">Mounting elevation still needed: {deferred.join(', ')}. These devices are deferred; other valid assignments can proceed.</p>}
    <details><summary>Configure circuit preview</summary>
      <form onSubmit={submit} onChange={clearPreview}>
        <fieldset disabled={busy}><legend>Circuit and panel</legend>
          <label><input type="checkbox" checked={missingOnly} onChange={(event) => setMissingOnly(event.target.checked)} />Propose only missing device routes</label>
          <fieldset disabled={!missingOnly}><legend>Reuse reviewed observed wiring</legend>
            <p>Select only paths belonging to this circuit and physically connected to the entered panel. Shared endpoints join; interior crossings do not. Stored elevations must match the service plane. Existing wiring stays unchanged.</p>
            {observedChoices.map(route => <label key={route.id}><input type="checkbox" checked={observedRoutes.includes(route.id)}
              onChange={event => setObservedRoutes(current => event.target.checked ? [...current, route.id] : current.filter(id => id !== route.id))} />Use observed route {route.id}</label>)}
            {observedChoices.length === 0 && <p>No reviewed observed paths in this saved layout. No circuit assignment is inferred from nearby drawing lines.</p>}
          </fieldset>
          <label className="studio-field">Circuit identifier<input name="circuit" maxLength={80} required defaultValue={initialConfiguration?.circuit_id ?? ''} /></label>
          <label className="studio-field">Installation method<select name="installation" required value={installation} onChange={(event) => setInstallation(event.target.value)}><option value="">Choose explicitly</option><option value="ceiling_service">Ceiling/service with verified wall drops</option><option value="underground">Underground with explicit floor passages</option></select></label>
          {installation === 'underground' && <>
            <p>Enter an absolute service elevation below this saved floor ({layout.geometry.floor.elevation_meters} m). Route depth is measured from that floor; passage locations use the panel and selected device coordinates.</p>
            <label><input name="floorPassages" type="checkbox" required defaultChecked={initialConfiguration?.floor_passages_confirmed === true} />Use floor passages at the entered panel and device positions for this planning route.</label>
          </>}
          {[['panelX', 'Circuit panel x (m)'], ['panelY', 'Circuit panel y (m)'], ['panelHeight', 'Circuit panel elevation (m)'], ['service', 'Circuit service elevation (m)']].map(([name, label]) => <label className="studio-field" key={name}>{label}<input name={name} type="number" step="any" required defaultValue={savedFields[name] ?? ''} /></label>)}
          <label className="studio-field">Circuit panel wall<select name="panelWall" defaultValue={initialConfiguration?.panel.wall_id ?? ''}>{wallOptions}</select></label>
          <label className="studio-field">Circuit graph spacing (m)<input name="step" type="number" min="0.1" max="5" step="0.1" defaultValue={initialConfiguration?.grid_step_meters ?? '0.5'} required /></label>
          <div className="circuit-preview-members">{orderNamed(layout.geometry.symbols, symbol => symbol.class.name).map((symbol) => <fieldset key={symbol.id}>
            <legend>{symbol.class.name} · {symbol.id}</legend>
            <label><input type="checkbox" checked={selected.includes(symbol.id)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, symbol.id] : current.filter((id) => id !== symbol.id))} />Include {symbol.class.name} · {symbol.id}</label>
            <label className="studio-field">Elevation for {symbol.id} (m)<input name={`height:${symbol.id}`} type="number" step="any" disabled={!selected.includes(symbol.id)} required={!missingOnly && selected.includes(symbol.id)} defaultValue={savedTargets.get(symbol.id)?.elevation_meters ?? ''} /></label>
            <label className="studio-field">Wall for {symbol.id}<select name={`wall:${symbol.id}`} disabled={!selected.includes(symbol.id)} defaultValue={savedTargets.get(symbol.id)?.wall_id ?? ''}>{wallOptions}</select></label>
          </fieldset>)}</div>
          <p>{selected.length}/32 devices selected. Coordinates come from the saved canonical layout; membership and elevations are not inferred.</p>
          <RoutingObstacles rows={obstacles} onChange={changeObstacles} disabled={busy} scope="Circuit" />
          <label><input type="checkbox" required />I confirm this circuit membership, panel position and installation inputs for planning.</label>
          <Button type="submit" disabled={!selected.length || selected.length > 32}>Preview shared circuit</Button>
        </fieldset>
      </form>
    </details>
    {busy && <p role="status">Planning shared circuit…</p>}
    {preview && <>
      <p role="status">Preview only: {preview.result.branches.length} devices; {preview.result.total_meters.toFixed(3)} m unique path ({preview.result.horizontal_meters.toFixed(3)} m horizontal + {preview.result.vertical_meters.toFixed(3)} m vertical). Not saved; no estimate or conductor quantities changed.</p>
      {preview.result.reused_observed_routes?.length > 0 && <p role="note">Reusing {preview.result.reused_observed_routes.length} explicitly assigned observed paths. Lengths above count new generated geometry only; existing paths are not duplicated or included again.</p>}
      <p>Entered device elevations are shared with 3D for this snapshot. Equipment dimensions remain illustrative. Saving does not approve electrical design or publish material quantities.</p>
      {preview.result.skipped_targets?.length > 0 && <p role="note">Existing canonical connections preserved: {preview.result.skipped_targets.map((item) => item.symbol_id).join(', ')}.</p>}
      {preview.result.unresolved_targets?.length > 0 && <ul aria-label="Unresolved device routes">{preview.result.unresolved_targets.map((item) => <li key={`${item.floor_id}:${item.symbol_id}`}>{item.symbol_id}: {item.reason.replaceAll('_', ' ').toLowerCase()}</li>)}</ul>}
      <Button disabled={busy || !preview.result.segments.length} onClick={save}>Save planning circuit</Button>
      <Button variant="outline" aria-pressed={show2D} onClick={() => setShow2D((value) => !value)}>{show2D ? 'Hide circuit 2D preview' : 'Compare circuit in 2D'}</Button>
      <Button variant="ghost" disabled={busy} onClick={clearPreview}>Discard circuit preview</Button>
      {show2D && <CanonicalLayoutCanvas geometry={layout.geometry} routeSegments={projectRoute(preview, layout)} visibility={{ blueprint: false, walls: true, rooms: true, symbols: true, routes: true }} />}
    </>}
  </section>
}
