import { useEffect, useRef, useState } from 'react'
import { orderNamed } from '../../utils/listOrder.js'
import { routingRequest } from '../../api/routing.js'
import { RoutingObstacles } from './RoutingObstacles.jsx'
import { obstacleRows, routingObstaclesFromRows } from './routeObstacles.js'

export function RoutingPanel({ layout, record, onSaved }) {
  const raw = record?.configuration?.obstacles
  let restored = [], blocked = false
  if (raw !== undefined && (!Array.isArray(raw) || raw.length)) {
    const configuration = record.configuration
    const floor = configuration.floors?.[0]
    const compatible = !record.stale && record.project_id === layout.project_id
      && record.layout_versions?.[String(layout.project_floor_id)] === layout.id
      && record.result?.algorithm === 'orthogonal_astar_v1'
      && (configuration.installation_method ?? 'ceiling_service') === 'ceiling_service'
      && configuration.floors?.length === 1 && !configuration.connectors?.length
      && floor?.floor_id === layout.project_floor_id && floor.expected_layout_version === layout.version_number
      && floor.offset_x === 0 && floor.offset_y === 0
    try {
      if (!compatible) throw new Error('Saved obstacles require their compatible floor configuration.')
      restored = obstacleRows(raw, layout.project_floor_id)
    } catch { blocked = true }
  }
  const snapshot = restored.length || blocked ? `${record.id}:${record.version_number}` : 'new'
  return <RoutingForm key={`${layout.project_id}:${layout.project_floor_id}:${layout.id}:${layout.version_number}:${snapshot}`}
    layout={layout} record={record} onSaved={onSaved} initialObstacles={restored} obstaclesBlocked={blocked} />
}

function RoutingForm({ layout, record, onSaved, initialObstacles, obstaclesBlocked }) {
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [obstacles, setObstacles] = useState(initialObstacles)
  const [hasError, setHasError] = useState(false)
  const messageRef = useRef(null)
  const requestRef = useRef(null)
  useEffect(() => () => requestRef.current?.abort(), [])
  useEffect(() => { if (hasError) messageRef.current?.focus() }, [hasError, message])
  async function submit(event) {
    event.preventDefault()
    if (obstaclesBlocked) return
    const form = new FormData(event.currentTarget)
    const number = (name) => Number(form.get(name))
    const wall = (name) => form.get(name) ? number(name) : null
    const symbol = layout.geometry.symbols.find((s) => s.id === form.get('symbol'))
    if (!symbol) return
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    setBusy(true)
    setHasError(false)
    setMessage('Calculating route…')
    try {
      const result = await routingRequest(layout.project_id, { signal: controller.signal, configuration: {
        floors: [{ floor_id: layout.project_floor_id, expected_layout_version: layout.version_number,
          service_elevation_meters: number('service'), offset_x: 0, offset_y: 0 }],
        panel: { floor_id: layout.project_floor_id, x: number('panelX'), y: number('panelY'), elevation_meters: number('panelHeight'), wall_id: wall('panelWall') },
        target: { floor_id: layout.project_floor_id, symbol_id: symbol.id, ...symbol.position, elevation_meters: number('targetHeight'), wall_id: wall('targetWall') },
        connectors: [], obstacles: routingObstaclesFromRows(obstacles, layout.project_floor_id),
        grid_step_meters: number('step'), alignment_confirmed: true, purpose: 'planning',
      } })
      if (controller.signal.aborted) return
      onSaved(result)
      setMessage(`Route version ${result.version_number} saved.`)
    } catch (error) { if (!controller.signal.aborted) { setHasError(true); setMessage(error.message) } }
    finally { if (!controller.signal.aborted) setBusy(false) }
  }
  return <section aria-label="Electrical routing">
    <h2>Electrical routing</h2>
    <p>Planning only. Enter absolute elevations in meters. Wall-mounted endpoints require a saved verified wall. Service paths cannot cross structural obstacles. This form routes one floor; multi-floor risers are supported by the routing API.</p>
    {initialObstacles.length > 0 && <p role="note">Saved route obstacles restored. Re-enter and confirm endpoint coordinates and elevations before recalculating.</p>}
    {obstaclesBlocked && <p role="alert">Saved obstacles cannot safely be restored in this single-floor ceiling form. Recalculation is blocked rather than dropping barriers. Reload the matching layout or use the circuit workflow for its saved installation configuration.</p>}
    {record && <p>Route version {record.version_number}: {record.result.horizontal_meters.toFixed(3)} m horizontal + {record.result.vertical_meters.toFixed(3)} m vertical = {record.result.total_meters.toFixed(3)} m total. {record.stale ? 'Layout changed — recalculate before use.' : 'Saved backend measurement.'}</p>}
    <details><summary>Generate / recalculate route</summary>
      <form onSubmit={submit}>
        <fieldset disabled={busy || obstaclesBlocked}><legend>Panel and service configuration</legend>
          {[['panelX', 'Panel x (m)'], ['panelY', 'Panel y (m)'], ['panelHeight', 'Panel elevation (m)'], ['service', 'Service elevation (m)'], ['targetHeight', 'Target elevation (m)']].map(([name, label]) => <label key={name}>{label}<input name={name} type="number" step="any" required /></label>)}
          <label>Grid spacing (m)<input name="step" type="number" min="0.1" max="5" step="0.1" defaultValue="0.5" required /></label>
          <label>Target symbol<select name="symbol" required>{orderNamed(layout.geometry.symbols, s => s.class.name).map((s) => <option key={s.id} value={s.id}>{s.class.name} — {s.id}</option>)}</select></label>
          {['panelWall', 'targetWall'].map((name) => <label key={name}>{name === 'panelWall' ? 'Panel wall' : 'Target wall'}<select name={name}><option value="">At service elevation (no wall attachment)</option>{orderNamed(layout.geometry.walls.filter((w) => w.status === 'verified'), w => w.id).map((w) => <option key={w.id} value={w.id}>Wall {w.id}</option>)}</select></label>)}
          <RoutingObstacles rows={obstacles} onChange={setObstacles} disabled={busy} scope="Route" />
          <label><input type="checkbox" required />I confirm these coordinates and service elevations for planning.</label>
          <button type="submit" disabled={!layout.geometry.symbols.length}>Calculate and save route</button>
        </fieldset>
      </form>
    </details>
    {message && <p ref={messageRef} role={hasError ? 'alert' : 'status'} tabIndex={hasError ? -1 : undefined}>{message}</p>}
  </section>
}
