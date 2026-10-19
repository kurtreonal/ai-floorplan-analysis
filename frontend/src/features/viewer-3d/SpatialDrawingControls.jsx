import { WiringTargetChooser } from '../detection-review/WiringTargetChooser.jsx'
import './spatialDrawing.css'

export function SpatialDrawingControls({drawing,tool,floorElevation,presentations}) {
  if(!drawing.active)return null
  return <>
    <div className="spatial-drawing-controls" role="group" aria-label="3D drawing controls">
      <strong>{tool==='wire'?'Draw wiring':'Draw walls'} · horizontal work plane</strong>
      <fieldset disabled={drawing.vertices.length>0}>
        {tool==='wire'?<label>Service elevation (m, project datum)<input type="number" min="-1000" max="10000" step="any"
          value={drawing.settings.elevation} onChange={e=>drawing.setOption('elevation',e.target.value)} /></label>
          :<><span>Floor elevation: {Number.isFinite(floorElevation)?`${floorElevation} m`:'not configured'}</span>
            {[['thickness','Wall thickness (m)'],['height','Wall height (m)'],['length','Exact wall length (m, optional)']].map(([key,label])=>
              <label key={key}>{label}<input type="number" min="0.001" max="1000" step="any" value={drawing.settings[key]} onChange={e=>drawing.setOption(key,e.target.value)} /></label>)}</>}
        {tool==='wire'&&<label>Circuit identifier (optional)<input maxLength={80} value={drawing.settings.circuit} onChange={e=>drawing.setOption('circuit',e.target.value)} /></label>}
        <label>Axis constraint<select value={drawing.settings.axis} onChange={e=>drawing.setOption('axis',e.target.value)}>
          <option value="none">None · Shift locks axis</option><option value="x">Plan X</option><option value="y">Plan Y</option></select></label>
      </fieldset>
      {(drawing.reason||drawing.error)&&<p role={drawing.error?'alert':'status'}>{drawing.error||drawing.reason}</p>}
      <div><button type="button" onClick={drawing.finish} disabled={!drawing.enabled || (tool==='wire'&&drawing.vertices.length<2)}>Done</button>
        <button type="button" onClick={drawing.cancel}>{tool==='wire'?'Cancel drawing':'Finish walls'}</button></div>
      {drawing.enabled&&<small>Click points · Enter finishes · Escape cancels the active stroke</small>}
    </div>
    {drawing.choices&&<WiringTargetChooser choices={drawing.choices} presentations={presentations}
      onPreview={drawing.preview} onChoose={drawing.choose} onCancel={drawing.cancelChoice} />}
  </>
}
