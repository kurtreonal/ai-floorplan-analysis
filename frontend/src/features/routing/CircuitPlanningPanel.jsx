import { useEffect, useRef, useState } from 'react'
import { previewCircuit } from '../../api/routing.js'
import { Button } from '../../components/ui/button.jsx'
import { CanonicalLayoutCanvas } from '../editor-2d/CanonicalLayoutCanvas.jsx'
import { projectRoute } from './routeProjection.js'

export function CircuitPlanningPanel({ layout, onPreview }) {
  const [selected, setSelected] = useState([])
  const [preview, setPreview] = useState(null)
  const [show2D, setShow2D] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const errorRef = useRef(null)
  const requestRef = useRef(null)
  useEffect(() => () => requestRef.current?.abort(), [])
  useEffect(() => { if (error) errorRef.current?.focus() }, [error])

  function clearPreview() {
    if (preview) { setPreview(null); onPreview(null) }
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
      onPreview(result)
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure.message)
    } finally { if (!controller.signal.aborted) setBusy(false) }
  }

  const walls = layout.geometry.walls.filter((wall) => wall.status === 'verified')
  const wallOptions = <><option value="">At service elevation; no wall attachment</option>{walls.map((wall) => <option key={wall.id} value={wall.id}>Wall {wall.id}</option>)}</>
  return <section aria-label="Shared circuit planning preview">
    <h2>Shared circuit preview</h2>
    <p>Assign saved devices to one circuit explicitly. Ceiling/service paths share a bounded graph; wall drops use your entered absolute elevations and verified wall attachments. This is a greedy planning preview, not a proven global optimum.</p>
    <details><summary>Configure circuit preview</summary>
      <form onSubmit={submit} onChange={clearPreview}>
        {error && <p ref={errorRef} role="alert" tabIndex={-1}>{error}</p>}
        <fieldset disabled={busy}><legend>Circuit and panel</legend>
          <label className="studio-field">Circuit identifier<input name="circuit" maxLength={80} required /></label>
          <label className="studio-field">Installation method<select name="installation" required defaultValue=""><option value="">Choose explicitly</option><option value="ceiling_service">Ceiling/service with verified wall drops</option></select></label>
          <p>Underground and underfloor routing are not implemented. Do not substitute a ceiling route for those legends.</p>
          {[['panelX', 'Circuit panel x (m)'], ['panelY', 'Circuit panel y (m)'], ['panelHeight', 'Circuit panel elevation (m)'], ['service', 'Circuit service elevation (m)']].map(([name, label]) => <label className="studio-field" key={name}>{label}<input name={name} type="number" step="any" required /></label>)}
          <label className="studio-field">Circuit panel wall<select name="panelWall">{wallOptions}</select></label>
          <label className="studio-field">Circuit graph spacing (m)<input name="step" type="number" min="0.1" max="5" step="0.1" defaultValue="0.5" required /></label>
          <div className="circuit-preview-members">{layout.geometry.symbols.map((symbol) => <fieldset key={symbol.id}>
            <legend>{symbol.class.name} · {symbol.id}</legend>
            <label><input type="checkbox" checked={selected.includes(symbol.id)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, symbol.id] : current.filter((id) => id !== symbol.id))} />Include {symbol.class.name} · {symbol.id}</label>
            <label className="studio-field">Elevation for {symbol.id} (m)<input name={`height:${symbol.id}`} type="number" step="any" disabled={!selected.includes(symbol.id)} required={selected.includes(symbol.id)} /></label>
            <label className="studio-field">Wall for {symbol.id}<select name={`wall:${symbol.id}`} disabled={!selected.includes(symbol.id)}>{wallOptions}</select></label>
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
      <p>Routes use entered elevations; device meshes retain illustrative mounting defaults. Physical mounting synchronization requires saved installation metadata.</p>
      <Button variant="outline" aria-pressed={show2D} onClick={() => setShow2D((value) => !value)}>{show2D ? 'Hide circuit 2D preview' : 'Compare circuit in 2D'}</Button>
      <Button variant="ghost" onClick={clearPreview}>Discard circuit preview</Button>
      {show2D && <CanonicalLayoutCanvas geometry={layout.geometry} routeSegments={projectRoute(preview, layout)} visibility={{ blueprint: false, walls: true, rooms: true, symbols: true, routes: true }} />}
    </>}
  </section>
}
