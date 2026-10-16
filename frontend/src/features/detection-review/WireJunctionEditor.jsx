import { useState } from 'react'
import { Button } from '../../components/ui/button.jsx'
import { deleteWireVertex, detachWireJunction, insertWireVertex, joinWireJunction } from './wireJunctions.js'

export function WireJunctionEditor({ wire, draft, disabled, onEdit }) {
  const [source, setSource] = useState(0)
  const [targetId, setTargetId] = useState('')
  const [segment, setSegment] = useState(0)
  const [percent, setPercent] = useState('50')
  const sourceIndex = Math.min(source, wire.points.length-1)
  const paths = draft.wirings.filter(w => w.id !== wire.id && w.disposition !== 'rejected' && !w.suppression_reason
    && (w.origin === 'generated') === (wire.origin === 'generated'))
  const target = paths.find(w => w.id === targetId)
  const segmentIndex = Math.min(segment, (target?.points.length ?? 2)-2)
  return <details><summary>Path vertices &amp; junctions</summary>
    <fieldset disabled={disabled}><legend>Edit complete path</legend>
      <label>Source vertex<select value={sourceIndex} onChange={event => setSource(Number(event.target.value))}>
        {wire.points.map((_, i) => <option key={i} value={i}>Point {i+1}</option>)}
      </select></label>
      <Button variant="outline" disabled={sourceIndex >= wire.points.length-1 || wire.points.length >= 2048}
        onClick={() => onEdit(current => insertWireVertex(current, wire.id, sourceIndex))}>Insert midpoint after vertex</Button>
      <Button variant="ghost" disabled={wire.points.length <= 2}
        onClick={() => onEdit(current => deleteWireVertex(current, wire.id, sourceIndex))}>Delete vertex</Button>
      {wire.junction_attachments?.some(a => a.point_index === sourceIndex) && <Button variant="outline"
        onClick={() => onEdit(current => detachWireJunction(current, wire.id, sourceIndex))}>Detach junction at vertex</Button>}
      <label>Connect to path<select value={targetId} onChange={event => {setTargetId(event.target.value);setSegment(0)}}>
        <option value="">Choose explicitly</option>{paths.map(w => <option key={w.id} value={w.id}>{w.id}{w.circuit_id ? ` · ${w.circuit_id}` : ' · circuit unassigned'}</option>)}
      </select></label>
      <label>Target segment<select value={segmentIndex} disabled={!target} onChange={event => setSegment(Number(event.target.value))}>
        {target?.points.slice(1).map((_, i) => <option key={i} value={i}>Point {i+1} → {i+2}</option>)}
      </select></label>
      <label>Position along target segment (%)<input type="number" min="0" max="100" step="any" value={percent} onChange={event => setPercent(event.target.value)} /></label>
      <Button variant="outline" disabled={!target || percent.trim()===''} onClick={() => onEdit(current =>
        joinWireJunction(current, wire.id, sourceIndex, targetId, segmentIndex, Number(percent)/100))}>Connect junction</Button>
      <p>Explicit connection only. This moves the source vertex and splits the target segment when needed. Circuit, installation and height must match; unknown measurements may remain unset for a 2D draft. Crossings are not junctions.</p>
    </fieldset>
  </details>
}
