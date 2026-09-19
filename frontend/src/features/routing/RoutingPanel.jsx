import { useState } from 'react'
import { routingRequest } from '../../api/routing.js'

export function RoutingPanel({ layout, record, onSaved }) {
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const number = (name) => Number(form.get(name))
    const wall = (name) => form.get(name) ? number(name) : null
    const symbol = layout.geometry.symbols.find((s) => s.id === form.get('symbol'))
    if (!symbol) return
    setBusy(true)
    setMessage('Calculating route…')
    try {
      const result = await routingRequest(layout.project_id, { configuration: {
        floors: [{ floor_id: layout.project_floor_id, expected_layout_version: layout.version_number,
          service_elevation_meters: number('service'), offset_x: 0, offset_y: 0 }],
        panel: { floor_id: layout.project_floor_id, x: number('panelX'), y: number('panelY'), elevation_meters: number('panelHeight'), wall_id: wall('panelWall') },
        target: { floor_id: layout.project_floor_id, symbol_id: symbol.id, ...symbol.position, elevation_meters: number('targetHeight'), wall_id: wall('targetWall') },
        connectors: [], obstacles: [], grid_step_meters: number('step'), alignment_confirmed: true, purpose: 'planning',
      } })
      onSaved(result)
      setMessage(`Route version ${result.version_number} saved.`)
    } catch (error) { setMessage(error.message) }
    finally { setBusy(false) }
  }
  return <section aria-label="Electrical routing">
    <h2>Electrical routing</h2>
    <p>Planning only. Enter absolute elevations in meters. Wall-mounted endpoints require a saved verified wall. Service paths cannot cross structural obstacles. This form routes one floor; multi-floor risers are supported by the routing API.</p>
    {record && <p>Route version {record.version_number}: {record.result.horizontal_meters.toFixed(3)} m horizontal + {record.result.vertical_meters.toFixed(3)} m vertical = {record.result.total_meters.toFixed(3)} m total. {record.stale ? 'Layout changed — recalculate before use.' : 'Saved backend measurement.'}</p>}
    <details><summary>Generate / recalculate route</summary>
      <form onSubmit={submit}>
        <fieldset disabled={busy}><legend>Panel and service configuration</legend>
          {[['panelX', 'Panel x (m)'], ['panelY', 'Panel y (m)'], ['panelHeight', 'Panel elevation (m)'], ['service', 'Service elevation (m)'], ['targetHeight', 'Target elevation (m)']].map(([name, label]) => <label key={name}>{label}<input name={name} type="number" step="any" required /></label>)}
          <label>Grid spacing (m)<input name="step" type="number" min="0.1" max="5" step="0.1" defaultValue="0.5" required /></label>
          <label>Target symbol<select name="symbol" required>{layout.geometry.symbols.map((s) => <option key={s.id} value={s.id}>{s.class.name} — {s.id}</option>)}</select></label>
          {['panelWall', 'targetWall'].map((name) => <label key={name}>{name === 'panelWall' ? 'Panel wall' : 'Target wall'}<select name={name}><option value="">At service elevation (no wall attachment)</option>{layout.geometry.walls.filter((w) => w.status === 'verified').map((w) => <option key={w.id} value={w.id}>Wall {w.id}</option>)}</select></label>)}
          <label><input type="checkbox" required />I confirm these coordinates and service elevations for planning.</label>
          <button type="submit" disabled={!layout.geometry.symbols.length}>Calculate and save route</button>
        </fieldset>
      </form>
    </details>
    {message && <p role="status">{message}</p>}
  </section>
}
