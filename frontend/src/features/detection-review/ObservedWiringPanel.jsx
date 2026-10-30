import { useState } from 'react'
import { Button } from '../../components/ui/button.jsx'
import { nextWiringId, parseWiringPoints } from './observedWiringDraft.js'
import { orderNamed } from '../../utils/listOrder.js'

function WireEditor({ wire, width, height, onApply, onRemove, onCancel, disabled }) {
  const [coordinates, setCoordinates] = useState(wire.points.map((point) => `${point.x},${point.y}`).join('\n'))
  const [error, setError] = useState(null)
  function apply() {
    try {
      const points = parseWiringPoints(coordinates, width, height)
      onApply({ ...wire, points, disposition: wire.id ? (wire.disposition === 'added' ? 'added' : 'corrected') : 'added',
        ...(wire.origin === 'generated' ? {suppression_reason:null} : {}) })
    } catch (failure) { setError(failure.message) }
  }
  return <fieldset className="demo-wiring-editor" disabled={disabled}>
    <legend>{wire.id || 'New visible wiring trace'}</legend>
    <label>Source-pixel points {wire.id}<textarea value={coordinates} rows={4}
      placeholder={'X,Y\nX,Y'} onChange={(event) => { setCoordinates(event.target.value); setError(null) }} /></label>
    <p role="note">{wire.origin === 'generated' ? 'Automatic A* draft.' : wire.path_origin === 'manual' ? 'Drawn path.' : 'Source drawing trace.'}</p>
    {wire.wiring_legend_name && <p>{wire.wiring_legend_name.replace(/ \[pdf-.*$/, '')}</p>}
    {error && <p role="alert">{error}</p>}
    <div className="demo-add-actions"><Button variant="outline" onClick={apply}>Apply wiring changes</Button>
    {wire.id ? <Button variant="outline" disabled={wire.disposition === 'rejected'} onClick={onRemove}>Remove wiring trace</Button>
      : <Button variant="ghost" onClick={onCancel}>Cancel new trace</Button>}</div>
  </fieldset>
}

export function ObservedWiringPanel({ wires, width, height, onChange, visible, onVisibilityChange, view, disabled = false,onCheck }) {
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
    <h2 id="observed-wiring-title">Wiring · {wires.filter((wire) => wire.disposition !== 'rejected').length} paths</h2>
    <p>Click a wire to edit or remove it. No item confirmation is required.</p>
    {onCheck && <Button data-check-wiring variant="outline" onClick={onCheck}>Check wiring</Button>}
    <label><input type="checkbox" checked={visible} onChange={(event) => onVisibilityChange(event.target.checked)} />Show wiring</label>
    {view === '3d' && <p role="note">Draft heights are illustrative unless set. Click wiring to edit its points; saving does not approve a circuit.</p>}
    <details><summary>Edit wiring points</summary>
    <p>Drawing traces and automatic A* drafts stay separate. Drafts are not measured circuits.</p>
    {orderNamed(wires.filter(wire => wire.disposition !== 'rejected'), wire => wire.id).map((wire) => <details key={wire.id}>
      <summary>{wire.id} · {wire.origin === 'generated' ? 'Automatic A* draft' : wire.path_origin === 'manual' ? 'Drawn path' : 'Drawing trace'}</summary>
      <WireEditor key={JSON.stringify(wire)} wire={wire} width={width} height={height}
        disabled={disabled}
        onApply={(updated) => onChange(wires.map((item) => item.id === wire.id ? updated : item))}
        onRemove={() => onChange(wires.map((item) => item.id === wire.id ? { ...item, disposition: 'rejected', ...(item.origin === 'generated' ? {suppression_reason:null} : {}) } : item))} />
    </details>)}
    <Button variant="outline" disabled={disabled || adding || wires.length >= 2048} onClick={() => { setAdding(true); setError(null) }}>Add visible wiring trace</Button>
    {error && <p role="alert">{error}</p>}
    {adding && <WireEditor wire={{ id: '', points: [], disposition: 'unresolved', completeness: 'partial', elevation_meters: null }}
      width={width} height={height} disabled={disabled} onApply={add} onCancel={() => setAdding(false)} />}
    </details>
  </section>
}
