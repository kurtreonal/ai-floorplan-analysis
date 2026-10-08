import { useEffect, useRef, useState } from 'react'
import { previewCircuit, saveCircuit } from '../../api/routing.js'
import { Button } from '../../components/ui/button.jsx'
import { CanonicalLayoutCanvas } from '../editor-2d/CanonicalLayoutCanvas.jsx'
import { projectRoute } from './routeProjection.js'

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
  if (configuration?.installation_method !== 'ceiling_service' || configuration.floors?.length !== 1
    || !configuration.targets?.length || configuration.targets.length > 32
    || configuration.connectors?.length || configuration.obstacles?.length) return null
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
  const [preview, setPreview] = useState(null)
  const [show2D, setShow2D] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
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
    retryRef.current = null
    previewRef.current = null
    if (preview) { setPreview(null); onPreview(null) }
  }

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
        setError(failure.message)
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
    clearPreview()
    let configuration
    try {
      if (!selected.length || selected.length > 32) throw new Error('Select between 1 and 32 devices for this circuit.')
      configuration = {
        circuit_id: form.get('circuit').trim(), installation_method: form.get('installation'),
        floors: [{ floor_id: layout.project_floor_id, expected_layout_version: layout.version_number,
          service_elevation_meters: number('service'), offset_x: 0, offset_y: 0 }],
        panel: { floor_id: layout.project_floor_id, x: number('panelX'), y: number('panelY'),
          elevation_meters: number('panelHeight'), wall_id: wall('panelWall') },
        targets: layout.geometry.symbols.filter((symbol) => selected.includes(symbol.id)).map((symbol) => ({
          floor_id: layout.project_floor_id, symbol_id: symbol.id, ...symbol.position,
          elevation_meters: number(`height:${symbol.id}`), wall_id: wall(`wall:${symbol.id}`),
        })),
        connectors: [], obstacles: [], grid_step_meters: number('step'), alignment_confirmed: true, purpose: 'planning',
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
      if (!controller.signal.aborted) setError(failure.message)
    } finally { if (!controller.signal.aborted) setBusy(false) }
  }

  const walls = layout.geometry.walls.filter((wall) => wall.status === 'verified')
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
    <p>Assign saved devices to one circuit explicitly. Ceiling/service paths share a bounded graph; wall drops use your entered absolute elevations and verified wall attachments. This is a greedy planning preview, not a proven global optimum.</p>
    <details><summary>Configure circuit preview</summary>
      <form onSubmit={submit} onChange={clearPreview}>
        <fieldset disabled={busy}><legend>Circuit and panel</legend>
          <label className="studio-field">Circuit identifier<input name="circuit" maxLength={80} required defaultValue={initialConfiguration?.circuit_id ?? ''} /></label>
          <label className="studio-field">Installation method<select name="installation" required defaultValue={initialConfiguration?.installation_method ?? ''}><option value="">Choose explicitly</option><option value="ceiling_service">Ceiling/service with verified wall drops</option></select></label>
          <p>Underground and underfloor routing are not implemented. Do not substitute a ceiling route for those legends.</p>
          {[['panelX', 'Circuit panel x (m)'], ['panelY', 'Circuit panel y (m)'], ['panelHeight', 'Circuit panel elevation (m)'], ['service', 'Circuit service elevation (m)']].map(([name, label]) => <label className="studio-field" key={name}>{label}<input name={name} type="number" step="any" required defaultValue={savedFields[name] ?? ''} /></label>)}
          <label className="studio-field">Circuit panel wall<select name="panelWall" defaultValue={initialConfiguration?.panel.wall_id ?? ''}>{wallOptions}</select></label>
          <label className="studio-field">Circuit graph spacing (m)<input name="step" type="number" min="0.1" max="5" step="0.1" defaultValue={initialConfiguration?.grid_step_meters ?? '0.5'} required /></label>
          <div className="circuit-preview-members">{layout.geometry.symbols.map((symbol) => <fieldset key={symbol.id}>
            <legend>{symbol.class.name} · {symbol.id}</legend>
            <label><input type="checkbox" checked={selected.includes(symbol.id)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, symbol.id] : current.filter((id) => id !== symbol.id))} />Include {symbol.class.name} · {symbol.id}</label>
            <label className="studio-field">Elevation for {symbol.id} (m)<input name={`height:${symbol.id}`} type="number" step="any" disabled={!selected.includes(symbol.id)} required={selected.includes(symbol.id)} defaultValue={savedTargets.get(symbol.id)?.elevation_meters ?? ''} /></label>
            <label className="studio-field">Wall for {symbol.id}<select name={`wall:${symbol.id}`} disabled={!selected.includes(symbol.id)} defaultValue={savedTargets.get(symbol.id)?.wall_id ?? ''}>{wallOptions}</select></label>
          </fieldset>)}</div>
          <p>{selected.length}/32 devices selected. Coordinates come from the saved canonical layout; membership and elevations are not inferred.</p>
          <label><input type="checkbox" required />I confirm this circuit membership, panel position and installation inputs for planning.</label>
          <Button type="submit" disabled={!selected.length || selected.length > 32}>Preview shared circuit</Button>
        </fieldset>
      </form>
    </details>
    {busy && <p role="status">Planning shared circuit…</p>}
    {preview && <>
      <p role="status">Preview only: {preview.result.branches.length} devices; {preview.result.total_meters.toFixed(3)} m unique path ({preview.result.horizontal_meters.toFixed(3)} m horizontal + {preview.result.vertical_meters.toFixed(3)} m vertical). Not saved; no estimate or conductor quantities changed.</p>
      <p>Entered device elevations are shared with 3D for this snapshot. Equipment dimensions remain illustrative. Saving does not approve electrical design or publish material quantities.</p>
      <Button disabled={busy} onClick={save}>Save planning circuit</Button>
      <Button variant="outline" aria-pressed={show2D} onClick={() => setShow2D((value) => !value)}>{show2D ? 'Hide circuit 2D preview' : 'Compare circuit in 2D'}</Button>
      <Button variant="ghost" disabled={busy} onClick={clearPreview}>Discard circuit preview</Button>
      {show2D && <CanonicalLayoutCanvas geometry={layout.geometry} routeSegments={projectRoute(preview, layout)} visibility={{ blueprint: false, walls: true, rooms: true, symbols: true, routes: true }} />}
    </>}
  </section>
}
