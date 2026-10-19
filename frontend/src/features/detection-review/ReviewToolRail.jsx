import { MousePointer2, Hand, Move, Pencil, Trash2, Plus, ScanLine, Lightbulb, Layers } from 'lucide-react'
import { Button } from '../../components/ui/button.jsx'

export function ReviewToolRail({ view, tool, onToolChange, onAdd, layers, setLayers, opacity, onOpacityChange, wiringControls }) {
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
        <Button variant="ghost" className="studio-rail-tool" aria-pressed={tool === 'wire'} onClick={() => onToolChange('wire')}><Pencil aria-hidden="true" />Draw wiring</Button>
        <Button variant="ghost" className="studio-rail-tool" aria-label="Add missing room" onClick={() => onAdd('room')}><ScanLine aria-hidden="true" />Add room</Button>
        <Button variant="ghost" className="studio-rail-tool" aria-label="Add missing wall" onClick={() => onToolChange('draw')}><Plus aria-hidden="true" />Add wall</Button>
        {['draw','move','delete'].includes(tool)&&<Button variant="outline" onClick={()=>onToolChange('select')}>Done editing walls</Button>}
      </>}
    </div>
    {view === '3d' && <div className="studio-rail-tools">
      <Button variant="ghost" className="studio-rail-tool" aria-pressed={tool === 'draw'} onClick={() => onToolChange('draw')}><Pencil aria-hidden="true" />Draw walls</Button>
      <Button variant="ghost" className="studio-rail-tool" aria-pressed={tool === 'wire'} onClick={() => onToolChange('wire')}><Pencil aria-hidden="true" />Draw wiring</Button>
    </div>}
    {wiringControls && <div className="studio-rail-wiring">{wiringControls}</div>}
    <fieldset className="studio-rail-layers"><legend><Layers size={14} aria-hidden="true" />Visible layers</legend>
      {[["walls", 'Architecture'], ['wallFootprints', 'Wall footprints'], ['rooms', 'Rooms'], ['symbols', 'Devices'], ['names', 'Device names'], ['dimensions', 'Wall measurements'], ['source', 'Original blueprint']].map(([key, label]) =>
        <label key={key}><input type="checkbox" checked={Boolean(layers[key])} disabled={view === '3d' && ['source', 'names', 'dimensions', 'wallFootprints'].includes(key)} onChange={(event) => setLayers((current) => ({ ...current, [key]: event.target.checked }))} />{label}{view === '3d' && ['source', 'names', 'dimensions', 'wallFootprints'].includes(key) ? ' (2D)' : ''}</label>)}
    </fieldset>
    {view === '2d' && layers.source && <label className="studio-rail-opacity">Blueprint opacity<input type="range" min="0.1" max="1" step="0.05" value={opacity} onChange={(event) => onOpacityChange(Number(event.target.value))} /></label>}
    <div className="studio-shared-model"><span className="mono">ONE SHARED DRAFT</span><p>Edit in 2D or 3D, then save. No per-item confirmation.</p></div>
  </aside>
}
