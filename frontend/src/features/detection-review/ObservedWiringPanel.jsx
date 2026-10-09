import { useState } from 'react'
import { Button } from '../../components/ui/button.jsx'
import { nextWiringId, parseWiringPoints } from './observedWiringDraft.js'

function WireEditor({ wire, width, height, onApply, onRemove, onCancel, disabled }) {
  const [coordinates, setCoordinates] = useState(wire.points.map((point) => `${point.x},${point.y}`).join('\n'))
  const [disposition, setDisposition] = useState(wire.disposition)
  const [completeness, setCompleteness] = useState(wire.completeness)
  const [error, setError] = useState(null)
  function apply() {
    try {
      const points = parseWiringPoints(coordinates, width, height)
      onApply({ ...wire, points, disposition, completeness })
    } catch (failure) { setError(failure.message) }
  }
  return <fieldset className="demo-wiring-editor" disabled={disabled}>
    <legend>{wire.id || 'New visible wiring trace'}</legend>
    <label>Source-pixel points {wire.id}<textarea value={coordinates} rows={4}
      placeholder={'X,Y\nX,Y'} onChange={(event) => { setCoordinates(event.target.value); setError(null) }} /></label>
    <label>Wiring decision {wire.id}<select value={disposition} onChange={(event) => setDisposition(event.target.value)}>
      <option value="unresolved">Unresolved</option><option value="accepted">Accept observed trace</option>
      <option value="corrected">Corrected trace</option><option value="added">Manually added</option><option value="rejected">Reject</option>
    </select></label>
    <label>Trace completeness {wire.id}<select value={completeness} onChange={(event) => setCompleteness(event.target.value)}>
      <option value="partial">Partial</option><option value="complete">Complete visible trace</option><option value="unreadable">Unreadable</option>
    </select></label>
    <p role="note">Apply changes before saving the draft. No circuit connection, installation type or elevation is inferred.</p>
    {error && <p role="alert">{error}</p>}
    <div className="demo-add-actions"><Button variant="outline" onClick={apply}>Apply wiring changes</Button>
    {wire.id ? <Button variant="outline" disabled={wire.disposition === 'rejected'} onClick={onRemove}>Remove wiring trace</Button>
      : <Button variant="ghost" onClick={onCancel}>Cancel new trace</Button>}</div>
  </fieldset>
}

export function ObservedWiringPanel({ wires, width, height, onChange, visible, onVisibilityChange, view, disabled = false }) {
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState(null)
  function add(wire) {
    try {
      onChange([...wires, { ...wire, id: nextWiringId(wires) }])
      setAdding(false)
      onVisibilityChange(true)
    } catch (failure) { setError(failure.message) }
  }
  return <section className="demo-wiring-panel" aria-labelledby="observed-wiring-title">
    <h2 id="observed-wiring-title">Visible wiring review</h2>
    <p>Trace only wiring visible on the blueprint. Purple dashed overlays are observations, not generated ceiling routes or calculated wire quantities. Draft saving needs no scale or height approval.</p>
    <label><input type="checkbox" checked={visible} disabled={view !== '2d'} onChange={(event) => onVisibilityChange(event.target.checked)} />Show observed wiring (2D only)</label>
    {view !== '2d' && <p role="note">Unmeasured observed traces are not projected into 3D. Use the measured canonical routing workspace for ceiling, wall and underground routes.</p>}
    {wires.map((wire) => <details key={wire.id}>
      <summary>{wire.id} · {wire.disposition === 'rejected' ? 'removed' : wire.disposition} · {wire.completeness}</summary>
      <WireEditor key={JSON.stringify(wire)} wire={wire} width={width} height={height}
        disabled={disabled}
        onApply={(updated) => onChange(wires.map((item) => item.id === wire.id ? updated : item))}
        onRemove={() => onChange(wires.map((item) => item.id === wire.id ? { ...item, disposition: 'rejected' } : item))} />
    </details>)}
    <Button variant="outline" disabled={disabled || adding || wires.length >= 2048} onClick={() => { setAdding(true); setError(null) }}>Add visible wiring trace</Button>
    {error && <p role="alert">{error}</p>}
    {adding && <WireEditor wire={{ id: '', points: [], disposition: 'unresolved', completeness: 'partial', elevation_meters: null }}
      width={width} height={height} disabled={disabled} onApply={add} onCancel={() => setAdding(false)} />}
  </section>
}
