import { useEffect,useRef,useState } from 'react'
import { adminAssemblies,adminMaterialCatalog,downloadAssemblyPriceList } from '../../api/materialPrices.js'
import { Button } from '../../components/ui/button.jsx'
import { legendDescription, groupLegendChoices } from '../../api/legendChoices.js'
import { notify } from '../../components/notifications.js'
import './adminCatalog.css'
import './reviewDecisions.css'

const types=[['simplex_outlet','Simplex outlet'],['duplex_outlet','Duplex outlet'],['switch_1gang','1-gang switch'],
  ['switch_2gang','2-gang switch'],['switch_3gang','3-gang switch'],['switch_3way','3-way switch'],
  ['data_simplex','Single data outlet'],['data_duplex','Duplex data outlet'],['cctv','CCTV camera'],
  ['light_single','Single-tube light'],['light_twin','Twin-tube light'],['downlight','Downlight'],['troffer','Troffer'],
  ['smoke_detector','Smoke detector'],['heat_detector','Heat detector'],['pull_station','Pull station'],
  ['horn_strobe','Horn / siren with strobe'],['pull_horn_strobe','Pull station with horn / strobe'],
  ['fire_bell','Fire alarm bell'],['bell_pull','Bell with pull station'],['door_chime','Door chime'],
  ['push_button','Push button'],['magnetic_contact','Magnetic contact'],['motion_detector','Motion detector'],
  ['keypad','Keypad'],['vibration_detector','Vibration detector'],['panelboard','Panelboard'],
  ['circuit_breaker','Circuit breaker'],['fire_panel','Fire alarm panel'],['voice_outlet','Telephone / voice outlet'],
  ['utility_box','Utility box'],['pull_box','Pull box'],['fan_controller','Fan controller']]
const blank=()=>({code:'',name:'',brand:'Panasonic',device_type:'simplex_outlet',is_default:false,
  expected_revision:0,specifications:'',scope:'Device and mounting parts. Shipping and labor excluded.',source_references:[],components:[{material_id:'',quantity:1}]})

export function AdminAssemblies(){
  const [record,setRecord]=useState(null),[materials,setMaterials]=useState([]),[editing,setEditing]=useState(null)
  const [assemblyChoices,setAssemblyChoices]=useState({})
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('')
  const [showGaps,setShowGaps]=useState(true)
  const nameRef=useRef(null)
  const [nameError,setNameError]=useState(''),[query,setQuery]=useState('')
  const formRef=useRef(null),editorOpen=Boolean(editing)
  useEffect(()=>{if(editorOpen)formRef.current?.scrollIntoView({block:'start',behavior:'instant'})},[editorOpen])
  useEffect(()=>{const request=new AbortController();Promise.all([adminAssemblies(null,null,{signal:request.signal}),adminMaterialCatalog({signal:request.signal})])
    .then(([data,catalog])=>{setRecord(data);setMaterials(catalog)}).catch(failure=>{if(!request.signal.aborted)setError(failure.message)})
    return()=>request.abort()},[])
  function edit(row){setShowGaps(false);setEditing(row?{...row,components:row.components.map(p=>({...p}))}:{...blank(),name:record?.name_examples?.simplex_outlet || 'Simplex outlet'});setError('');setMessage('')}
  function field(key,value){if(key==='name'){setNameError('');setError('')}setEditing(previous=>({...previous,[key]:value}))}
  function component(index,key,value){setEditing(previous=>({...previous,components:previous.components.map((part,i)=>i===index?{...part,[key]:value}:part)}))}
  const example=record?.name_examples?.[editing?.device_type] || types.find(([id])=>id===editing?.device_type)?.[1] || ''
  function changeType(value){setNameError('');setError('');setEditing(previous=>({...previous,device_type:value,name:!previous.name.trim() || previous.name===(record?.name_examples?.[previous.device_type] || types.find(([id])=>id===previous.device_type)?.[1])?record?.name_examples?.[value] || types.find(([id])=>id===value)?.[1]:previous.name}))}
  async function save(event){event.preventDefault();if(busy||!record?.writable)return
    setBusy(true);setError('');setMessage('')
    const data=Object.fromEntries(['code','name','brand','device_type','is_default','assumed','scope_complete','expected_revision','specifications','scope','source_references','components'].map(key=>[key,editing[key]]))
    data.components=data.components.map(part=>({material_id:Number(part.material_id),quantity:part.quantity}))
    data.source_references=data.source_references.map(line=>line.trim()).filter(Boolean)
    try{await adminAssemblies(data,editing.material_id);setEditing(null);setMessage('Assembly saved. Existing estimates are unchanged.');setRecord(await adminAssemblies())}
    catch(failure){setError(failure.message);if(failure.message.startsWith('Assembly name:')){setNameError(failure.message);requestAnimationFrame(()=>{nameRef.current?.focus();nameRef.current?.scrollIntoView({block:'center'})})}}finally{setBusy(false)}}
  const choices=materials.filter(row=>row.is_active&&!row.is_assembly&&['piece','unit','set'].includes(row.unit)&&row.unit_price!==null)
  const gaps=groupLegendChoices((record?.price_gaps||[]).map(gap=>({...gap,id:gap.legend_id,is_active:true})))
  const gapLabels={missing_product:'Product needed',missing_component_price:'Component price needed',default_required:'Product / specification choice needed',incomplete_components:'Components need confirmation'}
  function addForLegend(gap){setShowGaps(false);setEditing({...blank(),name:legendDescription(gap.name),device_type:gap.device_type,assumed:true});setError('');setMessage('')}
  async function downloadPrices(){
    setBusy(true);setError('')
    try{const blob=await downloadAssemblyPriceList(),url=URL.createObjectURL(blob),link=document.createElement('a')
      link.href=url;link.download='VED-Device-Price-List.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
      notify('Device price list downloaded.')
    }catch(failure){setError(failure.message)}finally{setBusy(false)}
  }
  return <section className="studio-panel admin-catalog" aria-label="Device assemblies">
    <div className="studio-panel-heading"><h2>Device assemblies</h2><div className="account-actions"><Button variant="outline" disabled={busy||!record?.assemblies.length} onClick={downloadPrices}>Download price list</Button><Button disabled={busy||!record?.writable} onClick={()=>edit(null)}>Add assembly</Button></div></div>
    <p>Build one complete device from priced parts. Choose the device type first, then name it and add its parts.</p>
    {record&&!record.writable&&<small role="note">Assembly storage needs database administrator setup.</small>}
    {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    {record&&<section className="admin-price-gaps" aria-label="Device pricing coverage">
      <div className="studio-panel-heading"><div><h3>Device pricing coverage</h3><p>{gaps.length ? `${gaps.length} device legends need attention.` : 'Every supported active device legend has a default assembly with priced components.'}</p></div>
        <Button type="button" variant="outline" aria-expanded={showGaps} onClick={()=>setShowGaps(!showGaps)}>{showGaps?'Hide list':'Show list'}</Button></div>
      {showGaps&&gaps.length>0&&<div className="studio-table-scroll"><table><thead><tr><th>Device legend</th><th>Needed</th><th>Action</th></tr></thead><tbody>{gaps.map(gap=>{
        const compatible=record.assemblies.filter((a,index,all)=>gap.compatible_material_ids.includes(a.material_id)&&all.findIndex(other=>other.material_id===a.material_id)===index)
        const choice=compatible.find(a=>String(a.material_id)===assemblyChoices[gap.id])||compatible[0]
        return <tr key={gap.id}><td>{legendDescription(gap.name)}</td><td>{gapLabels[gap.reason]}</td><td>{choice ? <div className="assembly-choice-action">{compatible.length>1&&<select aria-label={`Assembly for ${legendDescription(gap.name)}`} disabled={busy} value={choice.material_id} onChange={event=>setAssemblyChoices(current=>({...current,[gap.id]:event.target.value}))}>{compatible.map(a=><option key={a.material_id} value={a.material_id}>{a.brand} · {a.name} · {a.code||a.material_id}</option>)}</select>}<Button type="button" variant="outline" disabled={busy||!record.writable} onClick={()=>edit(choice)}>Edit assembly</Button></div> : <Button type="button" variant="outline" disabled={busy||!record.writable} onClick={()=>addForLegend(gap)}>Add assembly</Button>}</td></tr>
      })}</tbody></table></div>}
      <small>Complete missing products here. Client prices and designer choices keep their priority.</small>
    </section>}
    {editing&&<form className="admin-assembly-form" ref={formRef} onSubmit={save}><fieldset disabled={busy}>
      <div className="admin-assembly-fields">
        <label>Device type<select disabled={Boolean(editing.material_id)} value={editing.device_type} onChange={event=>changeType(event.target.value)}>{types.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
        <label>Assembly name<input ref={nameRef} aria-invalid={Boolean(nameError)} aria-describedby="assembly-name-help" placeholder={example} required maxLength="255" value={editing.name} disabled={Boolean(editing.material_id)} onChange={event=>field('name',event.target.value)} /><small id="assembly-name-help">Include the device type. Example: {example}.</small>{nameError && <small className="admin-form-error">{nameError}</small>}{!editing.material_id && <Button type="button" variant="ghost" onClick={()=>field('name',example)}>Use suggested name</Button>}</label>
        <label>Code<input required pattern="[A-Za-z0-9._-]+" maxLength="64" value={editing.code} disabled={Boolean(editing.material_id)} onChange={event=>field('code',event.target.value)} /></label>
        <label>Brand<input required maxLength="80" value={editing.brand} onChange={event=>field('brand',event.target.value)} /></label>

      </div>
      <label><input type="checkbox" checked={editing.is_default} onChange={event=>field('is_default',event.target.checked)} />Use as the default for this device type</label>
      <label><input type="checkbox" checked={editing.assumed||false} onChange={event=>field('assumed',event.target.checked)} />Representative planning assumption</label>
      <label><input type="checkbox" checked={editing.scope_complete!==false} onChange={event=>field('scope_complete',event.target.checked)} />All required device components included</label>
      <h3>Included parts</h3>{editing.components.map((part,index)=><div className="admin-assembly-part" key={index}>
        <label>Material<select aria-label={`Component ${index+1}`} required value={part.material_id} onChange={event=>component(index,'material_id',event.target.value)}><option value="">Choose a part</option>{choices.map(row=><option key={row.id} value={row.id}>{row.name} · {row.currency} {row.unit_price} / {row.unit}</option>)}</select></label>
        <label>Quantity<input aria-label={`Component quantity ${index+1}`} type="number" min="0.0001" max="1000" step="0.0001" required value={part.quantity} onChange={event=>component(index,'quantity',event.target.value)} /></label>
        <Button variant="ghost" type="button" disabled={editing.components.length===1} onClick={()=>field('components',editing.components.filter((_,i)=>i!==index))}>Remove</Button>
      </div>)}
      <Button variant="outline" type="button" disabled={editing.components.length>=32} onClick={()=>field('components',[...editing.components,{material_id:'',quantity:1}])}>Add part</Button>
      <label>Includes / excludes<input required maxLength="500" value={editing.scope} onChange={event=>field('scope',event.target.value)} /></label>
      <label>Product specifications<input maxLength="500" placeholder="Rating, CAT category or camera technology" value={editing.specifications} onChange={event=>field('specifications',event.target.value)} /></label>
      <label>Source links<textarea rows="3" value={editing.source_references.join('\n')} placeholder="One manufacturer or seller link per line" onChange={event=>field('source_references',event.target.value.split('\n'))}/></label>
      <div className="admin-catalog-toolbar"><Button type="submit">{busy?'Saving…':'Save assembly'}</Button><Button variant="ghost" type="button" onClick={()=>setEditing(null)}>Cancel</Button></div>
    </fieldset></form>}
    <div className="admin-catalog-toolbar"><input type="search" aria-label="Search assemblies" placeholder="Search device or brand" value={query} onChange={event=>setQuery(event.target.value)}/></div>
    <div className="material-import-table"><table><thead><tr><th>Device</th><th>Brand</th><th>Whole-unit price</th><th>Default</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{record?.assemblies.filter(row=>`${row.name} ${row.brand}`.toLowerCase().includes(query.toLowerCase())).map(row=><tr key={row.material_id}><td>{row.name}</td><td>{row.brand}</td><td>{row.unit_price===null?'Missing component price':`${row.currency} ${Number(row.unit_price).toLocaleString('en-PH',{minimumFractionDigits:2})}`}</td><td>{row.is_default?'Default':'—'}</td><td><Button variant="ghost" disabled={busy} onClick={()=>edit(row)}>Edit parts</Button></td></tr>)}</tbody></table></div>
    {record&&!record.assemblies.length&&<small>No assemblies yet. Add priced parts from the material catalog.</small>}
  </section>
}
