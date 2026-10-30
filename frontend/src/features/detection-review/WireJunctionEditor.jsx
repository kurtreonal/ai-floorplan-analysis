import { useState } from 'react'
import { Button } from '../../components/ui/button.jsx'
import { deleteWireVertex, detachWireJunction, insertWireVertex } from './wireJunctions.js'

export function WireJunctionEditor({ wire, disabled, onEdit }) {
  const [source, setSource] = useState(0)
  const sourceIndex = Math.min(source, wire.points.length-1)
  return <details><summary>Bends &amp; wire joins</summary>
    <p>Drag a free endpoint onto a device or compatible path. The magnet previews the connection; release to connect. Crossings alone never connect.</p>
    <fieldset disabled={disabled}><legend>Edit complete path</legend>
      <label>Choose a point on this wire<select value={sourceIndex} onChange={event => setSource(Number(event.target.value))}>
        {wire.points.map((_, i) => <option key={i} value={i}>Point {i+1}</option>)}
      </select></label>
      <Button variant="outline" disabled={sourceIndex >= wire.points.length-1 || wire.points.length >= 2048}
        onClick={() => onEdit(current => insertWireVertex(current, wire.id, sourceIndex))}>Add bend after this point</Button>
      <Button variant="ghost" disabled={wire.points.length <= 2}
        onClick={() => onEdit(current => deleteWireVertex(current, wire.id, sourceIndex))}>Remove point</Button>
      {wire.junction_attachments?.some(a => a.point_index === sourceIndex) && <Button variant="outline"
        onClick={() => onEdit(current => detachWireJunction(current, wire.id, sourceIndex))}>Disconnect this join</Button>}
    </fieldset>
  </details>
}
