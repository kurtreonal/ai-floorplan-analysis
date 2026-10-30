import {useState} from 'react'
import {Button} from '../../components/ui/button.jsx'
import {heightTargetIds,applyWireHeights} from './wireJunctions.js'

export function WireHeightEditor({draft,wire,groupIds=[],defaultHeight,onApply,focus}){
  const group=groupIds.includes(wire.id)?groupIds:[]
  const [scope,setScope]=useState(group.length>1?'group':'selected')
  const [height,setHeight]=useState(wire.height_above_floor_meters>=0 && wire.installation_method!=='concealed_under_floor'?wire.height_above_floor_meters ?? defaultHeight ?? '':defaultHeight ?? '')
  const [depth,setDepth]=useState(wire.installation_method==='concealed_under_floor'?Math.abs(wire.height_above_floor_meters ?? 0):0)
  const [onlyMissing,setOnlyMissing]=useState(true),[message,setMessage]=useState(''),[error,setError]=useState('')
  const active=draft.wirings.filter(w=>w.disposition!=='rejected' && !w.suppression_reason)
  const supported=active.filter(w=>['concealed_in_ceiling','concealed_under_floor'].includes(w.installation_method))
  const seeds=scope==='group'?group:scope==='all'?supported.map(w=>w.id):scope==='placement'?active.filter(w=>w.installation_method===wire.installation_method).map(w=>w.id):[wire.id]
  let targets
  try{targets=heightTargetIds(draft,seeds)}
  catch{return <p role="alert">Some saved wire joins disagree. Review Start &amp; end connections or Bends &amp; wire joins before applying shared heights.</p>}
  const rows=active.filter(w=>targets.has(w.id))
  const below=rows.some(w=>w.installation_method==='concealed_under_floor'),above=rows.some(w=>w.installation_method!=='concealed_under_floor')
  function apply(){setError('');setMessage('');try{const next=applyWireHeights(draft,seeds,{height,depth,onlyMissing});const count=next.wirings.filter((w,index)=>w!==draft.wirings[index]).length;if(!count){setMessage('These paths already have heights. Clear “Only fill missing heights” to replace them.');return}onApply(next);setMessage(`${count} paths updated in this draft. Save changes to keep them.`)}catch(e){setError(e.message)}}
  return <section className="wire-height-editor" aria-label="Apply wiring heights"><label>Apply to<select value={scope} onChange={event=>{setScope(event.target.value);setMessage('')}}><option value="selected">Selected path and joined segments</option>{group.length>1 && <option value="group">BOM group · {group.length} paths</option>}<option value="placement">All paths with this placement</option><option value="all">All ceiling and under-floor paths</option></select></label>
    <small>{rows.length} paths selected. Joined segments stay together.</small>
    {above && <label>Height above finished floor (m)<input data-wire-height autoFocus={focus} type="number" min="-1000" max="10000" step="0.01" value={height} onChange={event=>setHeight(event.target.value)}/></label>}
    {below && <label>Depth below finished floor (m)<input data-wire-height={!above || undefined} autoFocus={focus && !above} type="number" min="0" max="1000" step="0.01" value={depth} onChange={event=>setDepth(event.target.value)}/><small>0 m means floor level.</small></label>}
    <label className="wire-height-check"><input type="checkbox" checked={onlyMissing} onChange={event=>setOnlyMissing(event.target.checked)}/>Only fill missing heights</label><small>Existing heights are kept. Clear this option to replace them.</small>
    <Button type="button" variant="outline" disabled={!rows.length} onClick={apply}>Apply to {rows.length} paths</Button><small>Device heights, circuits and path positions stay unchanged.</small>
    {message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
  </section>
}
