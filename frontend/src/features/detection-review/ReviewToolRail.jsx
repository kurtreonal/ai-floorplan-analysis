import { MousePointer2, Hand, Move, Pencil, Trash2, Plus, ScanLine, Lightbulb, Layers } from 'lucide-react'
import { Button } from '../../components/ui/button.jsx'

export function ReviewToolRail({ view, tool, onToolChange, onAdd, onConnectWalls, layers, setLayers, opacity, onOpacityChange }) {
  return <aside className="studio-review-rail" aria-label="Plan editing tools">
    <span className="mono studio-rail-kicker">{view === '3d' ? '3D NAVIGATION' : 'EDIT PLAN'}</span>
    <div className="studio-rail-tools">
      {[[MousePointer2, 'select', 'Select & move devices'], [Hand, 'pan', 'Pan']].map(([Icon, value, label]) =>
        <Button key={value} variant="ghost" className="studio-rail-tool" aria-pressed={tool === value}
          onClick={() => onToolChange(value)}><Icon aria-hidden="true" />{label}</Button>)}
      {view === '2d' && <>
        {[[Move, 'move', 'Move Walls'], [Pencil, 'draw', 'Draw Walls'], [Trash2, 'delete', 'Delete Walls']].map(([Icon, value, label]) =>
          <Button key={value} variant="ghost" className="studio-rail-tool" aria-pressed={tool === value}
            onClick={() => onToolChange(value)}><Icon aria-hidden="true" />{label}</Button>)}
        <Button variant="ghost" className="studio-rail-tool" aria-label="Add missing symbol" onClick={() => onAdd('symbol')}><Lightbulb aria-hidden="true" />Add device</Button>
        <Button variant="ghost" className="studio-rail-tool" aria-label="Add missing room" onClick={() => onAdd('room')}><ScanLine aria-hidden="true" />Add room</Button>
        <Button variant="ghost" className="studio-rail-tool" aria-label="Add missing wall" onClick={() => onAdd('wall')}><Plus aria-hidden="true" />Add wall</Button>
      </>}
      <Button variant="outline" className="studio-rail-tool" onClick={onConnectWalls}><ScanLine aria-hidden="true" />Connect walls</Button>
    </div>
    <fieldset className="studio-rail-layers"><legend><Layers size={14} aria-hidden="true" />Visible layers</legend>
      {[["walls", 'Architecture'], ['rooms', 'Room proposals'], ['symbols', 'Devices'], ['names', 'Device names'], ['source', 'Original blueprint']].map(([key, label]) =>
        <label key={key}><input type="checkbox" checked={layers[key]} disabled={view === '3d' && ['source', 'names'].includes(key)} onChange={(event) => setLayers((current) => ({ ...current, [key]: event.target.checked }))} />{label}{view === '3d' && ['source', 'names'].includes(key) ? ' (2D)' : ''}</label>)}
    </fieldset>
    {view === '2d' && layers.source && <label className="studio-rail-opacity">Blueprint opacity<input type="range" min="0.1" max="1" step="0.05" value={opacity} onChange={(event) => onOpacityChange(Number(event.target.value))} /></label>}
    <div className="studio-shared-model"><span className="mono">ONE SHARED DRAFT</span><p>2D and 3D use the same positions. Proposals need your review before canonical approval.</p></div>
  </aside>
}
