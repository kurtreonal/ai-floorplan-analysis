import { useState } from 'react'
import { MousePointer2, Move, Pencil, Trash2, ScanLine, Lightbulb, Layers, Cable, X, Ruler } from 'lucide-react'
import { Button } from '../../components/ui/button.jsx'
import { orderNamed } from '../../utils/listOrder.js'

export function ReviewToolRail({ view, tool, onToolChange, onAdd, layers, setLayers, opacity, onOpacityChange, wiringControls, rooms = [], selectedRoomId, onRoomSelect,onDisplayLayout,readOnly=false }) {
  const [section, setSection] = useState(null)
  const twoD = view === '2d'
  const action = (Icon, label, active, onClick, disabled = false) => <Button variant="ghost" size="icon" disabled={disabled} title={disabled ? `${label} — available in ${label === 'Move selected in 3D' ? '3D':'2D'}` : label} aria-label={label} aria-pressed={active} onClick={onClick}><Icon size={19} aria-hidden="true" /></Button>
  return <aside className="studio-review-rail" aria-label="Plan editing tools">
    <div className="studio-icon-rail">
      {action(MousePointer2,twoD && !readOnly ? 'Select & move':'Select',tool === 'select',() => onToolChange('select'))}
      {!readOnly && action(Move,'Move selected in 3D',tool === 'transform',() => onToolChange('transform'),twoD)}
      {!readOnly && action(Pencil,'Draw walls',tool === 'draw',() => onToolChange('draw'))}
      {!readOnly && action(Lightbulb,'Add device',tool === 'place-device',() => onAdd('symbol'),!twoD)}
      {!readOnly && action(Trash2,'Delete walls',tool === 'delete',() => onToolChange('delete'),!twoD)}
      <hr />
      {[[Cable,'Wiring'],[ScanLine,'Rooms'],[Layers,'Layers']].map(([Icon,label]) =>
        <Button key={label} variant="ghost" size="icon" title={label} aria-label={label} aria-expanded={section === label}
          onClick={() => setSection(current => current === label ? null : label)}><Icon size={19} aria-hidden="true" /></Button>)}
      {action(Ruler,'Ruler',tool === 'ruler',() => {setSection(null);onToolChange(tool === 'ruler' ? 'select':'ruler')} ,!twoD)}
    </div>
    <div className="studio-tool-flyout" hidden={!section}>
      <header><strong>{section}</strong><Button variant="ghost" size="icon" aria-label="Close tool options" onClick={() => setSection(null)}><X size={16} aria-hidden="true" /></Button></header>
      <div hidden={section !== 'Wiring'} className="studio-rail-wiring">
        {!readOnly && <Button variant="outline" aria-pressed={tool === 'wire'} onClick={() => onToolChange('wire')}><Cable size={15} aria-hidden="true" />Draw wiring</Button>}
        {wiringControls}
      </div>
      <div hidden={section !== 'Rooms'}>
      <label className="studio-room-choice">Review one room<select aria-label="Review room" value={selectedRoomId || ''} onChange={event => onRoomSelect?.(event.target.value)}>
        <option value="">Hide room proposals</option>
        {orderNamed(rooms.filter(r => r.disposition !== 'rejected'), r => r.name || r.id).map(r => <option key={r.id} value={r.id}>{r.name || r.id}</option>)}
      </select></label>
      {!readOnly && <Button variant="outline" disabled={!twoD} title={!twoD ? 'Add rooms in 2D' : undefined} aria-label="Add missing room" onClick={() => onAdd('room')}>Add room</Button>}
      </div>
      <div hidden={section !== 'Layers'}>
    <fieldset className="studio-rail-layers"><legend><Layers size={14} aria-hidden="true" />Visible layers</legend>
      {[["walls", 'Architecture'], ['wallFootprints', 'Wall footprints'], ['symbols', 'Devices'], ['names', 'Device names'], ['dimensions', 'Measurements'], ['source', 'Original blueprint']].map(([key, label]) =>
        <label key={key}><input type="checkbox" checked={Boolean(layers[key])} disabled={!twoD && ['source', 'names', 'wallFootprints'].includes(key)} onChange={(event) => setLayers((current) => ({ ...current, [key]: event.target.checked }))} />{label}</label>)}
    </fieldset>
    <label className="studio-rail-opacity">Blueprint opacity<input type="range" disabled={!twoD || !layers.source} min="0.1" max="1" step="0.05" value={opacity} onChange={(event) => onOpacityChange(Number(event.target.value))} /></label>
    {onDisplayLayout && <Button variant="outline" onClick={()=>{setSection(null);onDisplayLayout()}}>Display / print layout</Button>}
      </div>
    </div>
  </aside>
}
