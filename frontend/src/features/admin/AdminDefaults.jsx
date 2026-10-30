import { useEffect,useState } from 'react'
import { applicationDefaults } from '../../api/applicationDefaults.js'
import { Button } from '../../components/ui/button.jsx'
import {adminMaterialCatalog} from '../../api/materialPrices.js'

export function AdminDefaults() {
  const [record,setRecord]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  const [materials,setMaterials]=useState([])
  useEffect(()=>{const request=new AbortController();Promise.all([applicationDefaults(null,request.signal),adminMaterialCatalog({signal:request.signal})]).then(([r,m])=>{setRecord(r);setMaterials(m)}).catch(failure=>{if(!request.signal.aborted)setError(failure.message)});return()=>request.abort()},[])
  async function save(event){event.preventDefault();if(!record?.writable||busy)return
    const data=new FormData(event.currentTarget);setBusy(true);setError('')
    try{setRecord(await applicationDefaults({expected_revision:record.revision,paper_size:data.get('paper_size'),
      scale_denominator:Number(data.get('scale_denominator')),outlet_center_height_meters:Number(data.get('outlet_center_height_meters')),
      ceiling_height_meters:Number(data.get('ceiling_height_meters')),
      planning_conductor_count:Number(data.get('planning_conductor_count')),
      switch_center_height_meters:Number(data.get('switch_center_height_meters')),display_units:data.get('display_units'),
      ...Object.fromEntries(['lighting','power','data'].map(key=>[`${key}_wire_material_id`,data.get(`${key}_wire_material_id`)?Number(data.get(`${key}_wire_material_id`)):null])),
      ...Object.fromEntries(['editor_snapping','show_blueprint','show_walls','show_symbols','show_wiring'].map(key=>[key,data.has(key)]))}))}
    catch(failure){setError(failure.message)}finally{setBusy(false)}}
  return <fieldset><legend>Admin defaults</legend><p>Shared starting values. Explicit plan measurements and Designer overrides are preserved.</p>
    {record && <form key={record.revision} onSubmit={save}><fieldset disabled={busy || !record.writable}>
      <details><summary>Wire defaults by layout</summary>{[['lighting','Lighting'],['power','Power'],['data','Data']].map(([key,label])=><label key={key} className="studio-field">{label} wire / cable<select name={`${key}_wire_material_id`} defaultValue={record.settings[`${key}_wire_material_id`] || ''}><option value="">No default</option>{materials.filter(m=>m.is_active && ['meter','length','roll'].includes(m.unit) && /wire|cable/i.test(m.name) && !/patchcord|patch cord|connector|lug|tray/i.test(m.name) && (/cat[5678]|utp|fiber|fibre|coax|communications?|telephone|signal/i.test(m.name)===(key==='data'))).map(m=><option key={m.id} value={m.id}>{m.name} · {m.unit}</option>)}</select></label>)}</details>
      <label className="studio-field">Default paper size<select name="paper_size" defaultValue={record.settings.paper_size}>{['A1','A2','A3','A4','A5'].map(value=><option key={value}>{value}</option>)}</select></label>
      <label className="studio-field">Estimated individual wires per power / lighting path<input type="number" name="planning_conductor_count" min="1" max="1000" step="1" required defaultValue={record.settings.planning_conductor_count ?? 3}/><small>Used only when the drawing or saved circuit has no wire count. These quantities stay estimated. Data cables are measured as complete cables.</small></label>
      <label className="studio-field">Default scale 1:N<input type="number" name="scale_denominator" min="1" max="100000" step="any" required defaultValue={record.settings.scale_denominator}/></label>
      <label className="studio-field">Default ceiling height (m)<input type="number" name="ceiling_height_meters" min="0.01" max="100" step="0.01" required defaultValue={record.settings.ceiling_height_meters}/></label>
      <small>Planning assumption for automatic walls, ceiling wiring and light connections—not a detected dimension.</small>
      {[['outlet','Outlet'],['switch','Switch']].map(([key,label])=><label className="studio-field" key={key}>{label} center height above finished floor (m)<input type="number" name={`${key}_center_height_meters`} min="0" max="100" step="any" required defaultValue={record.settings[`${key}_center_height_meters`]}/></label>)}
      <label className="studio-field">Default display units<select name="display_units" defaultValue={record.settings.display_units}><option value="metric">Metric (m)</option><option value="imperial">Imperial (ft)</option></select></label>
      <p>Editor starting values · personal preferences take priority.</p>
      {[['editor_snapping','Drawing magnets'],['show_blueprint','Blueprint'],['show_walls','Walls'],['show_symbols','Devices'],['show_wiring','Wiring']].map(([key,label])=><label key={key}><input name={key} type="checkbox" defaultChecked={record.settings[key]}/>{label}</label>)}
      <Button disabled={busy || !record.writable} type="submit">{busy?'Saving…':'Save shared defaults'}</Button>
    </fieldset></form>}
    {record && !record.writable && <small role="note">Shared-default storage needs database administrator setup before changes can be saved.</small>}
    {record?.revision>0 && <small role="status">Shared defaults saved.</small>}{error && <p role="alert">{error}</p>}
  </fieldset>
}
