import {useEffect,useRef,useState} from 'react'
import {saveMaterialSelection} from '../../api/materialSelection.js'
import {Button} from '../../components/ui/button.jsx'
import {ConduitProductInput} from '../estimation/ConduitProductInput.jsx'
import {WorkspaceGuide} from './WorkspaceGuide.jsx'

const money=product=>product?.unit_price==null?'Price unavailable':new Intl.NumberFormat(undefined,{style:'currency',currency:product.currency || 'PHP'}).format(Number(product.unit_price))

export function WorkspaceProductEditor({projectId,floorPlanId,candidateRunId,item,kind,planning,onSaved,onClose,focusField=''}) {
  const device=kind==='symbol'
  const rows=planning.items || []
  const row=rows.find(r=>device?r.kind==='device' && r.symbol_ids?.includes(item.id):r.material_kind==='wire' && r.path_ids?.includes(item.id))
  const classId=item.class_id ?? row?.class_id
  const group=device?planning.device_groups?.find(g=>g.class_id===classId):null
  const products=device?group?.materials || []:planning.wire_materials || []
  const saved=planning.material_selection?.itemMaterials?.[`${device?'device':'wire'}:${item.id}`]
  const current=saved?.candidate_run_id===candidateRunId && (!device || saved.class_id===classId) && products.some(p=>p.id===saved.material_id)?saved:null
  const [material,setMaterial]=useState(String(current?.material_id || row?.material_id || ''))
  const [conduit,setConduit]=useState(String(current?.conduit_id || rows.find(r=>r.material_kind==='conduit' && r.path_ids?.includes(item.id))?.material_id || ''))
  const [count,setCount]=useState(current?.conductor_count ?? row?.conductor_count ?? planning.material_selection?.conductorCount ?? planning.default_conductor_count ?? '')
  const [length,setLength]=useState(current?.wire_meters_per_unit ?? '')
  const [conduitLength,setConduitLength]=useState(current?.conduit_meters_per_unit ?? '')
  const [countEdited,setCountEdited]=useState(false)
  const form=useRef(null)
  const [busy,setBusy]=useState(false),[error,setError]=useState('')
  const retry=useRef(null)
  const product=products.find(p=>String(p.id)===material)
  const rule=planning.wire_conduit_pairs?.find(p=>String(p.wire_material_id)===material)
  const allowed=new Set([rule?.conduit_material_id,rule?.under_floor_conduit_material_id,...(rule?.conduit_options || [])])
  const conduits=(planning.conduit_materials || []).filter(p=>allowed.has(p.id))
  const displayedConduit=allowed.has(Number(conduit))?conduit:String((item.installation_method==='concealed_under_floor'?rule?.under_floor_conduit_material_id:null) || rule?.conduit_material_id || '')
  const conduitProduct=conduits.find(p=>String(p.id)===displayedConduit)
  const conduitPackLength=conduitProduct?.meters_per_unit || (Number(displayedConduit)===rule?.under_floor_conduit_material_id?rule?.under_floor_meters_per_unit:rule?.conduit_meters_per_unit)
  const singleWire=/\b(?:THHN|THW|single[ -]?core|single conductor)\b/i.test(product?.name || '')
  const assumedCount=!countEdited && Boolean(current?.conductor_count_assumed ?? row?.conductor_count_assumed ?? (current?.conductor_count==null && row?.conductor_count==null && planning.material_selection?.conductorCount==null))
  const focusHelp={device:'Choose the brand and product for this device.',wire:'Choose the wire or complete cable for this connected network.',conductors:'Check the number of separate wires following this path. The starting value is filled in for you.','wire-length':'Check the metres supplied in one roll or pack.','conduit-length':'Check the metres supplied in one pipe or tubing length.',conduit:'Choose a protective conduit paired with the selected wiring.'}[focusField]
  useEffect(()=>{if(!focusField)return;const field=form.current?.querySelector(`[data-workspace-field="${focusField}"]`);field?.querySelector('input,select')?.focus({preventScroll:true});field?.scrollIntoView({block:'nearest'})},[focusField])
  const ids=device?[item.id]:row?.path_ids || [item.id]
  async function save(event,reset=false) {
    event?.preventDefault();setBusy(true);setError('')
    const choices={...planning.material_selection?.itemMaterials}
    for(const id of ids){
      const key=`${device?'device':'wire'}:${id}`
      if(reset)delete choices[key]
      else choices[key]={kind:device?'device':'wire',candidate_run_id:candidateRunId,material_id:Number(material),...(device?{class_id:classId}:{conduit_id:Number(displayedConduit),...(singleWire && count!=='' && (countEdited || current?.conductor_count!=null)?{conductor_count:Number(count),conductor_count_assumed:assumedCount}:{}),...(length!==''?{wire_meters_per_unit:Number(length)}:{}),...(conduitLength!==''?{conduit_meters_per_unit:Number(conduitLength)}:{})})}
    }
    const settings={itemMaterials:choices},serialized=JSON.stringify(settings)
    if(retry.current?.serialized!==serialized)retry.current={serialized,requestId:crypto.randomUUID(),expectedVersion:planning.material_selection_revision || 0}
    try {await saveMaterialSelection(projectId,{floorPlanId,...retry.current,settings});onSaved();onClose()}
    catch(e){setError(e.message)}finally{setBusy(false)}
  }
  return <form ref={form} className="workspace-product-form" data-focus-field={focusField || (device?'device':'')} onSubmit={save}><p>{device?'Only this device.':`Connected wiring network · ${ids.length} ${ids.length===1?'path':'paths'}.`}</p>
    {focusHelp && <p className="workspace-field-guidance" role="status">{focusField==='conductors' && product && !singleWire?'This is a complete cable. Its internal wires do not need a separate conductor count.':focusField==='wire-length' && product?.unit==='meter' || focusField==='conduit-length' && conduitProduct?.unit==='meter'?'This product is sold per metre, so no pack length is needed.':focusHelp}</p>}
    <label className="studio-field" data-workspace-field={device?'device':'wire'}>{device?'Brand / product':'Wire / cable product'}<select required value={material} onChange={e=>{setMaterial(e.target.value);setConduit('');setLength('');setConduitLength('')}}><option value="">Choose a compatible product</option>{products.map(p=><option key={p.id} value={p.id}>{p.brand?`${p.brand} · `:''}{p.name}</option>)}</select></label>
    {!products.length && <p role="status">{device && !group?'This device is outside this layout or has no assigned symbol. Check its symbol or change the layout type in floor-plan Options.':'No compatible products available. Ask Admin to add a product for this symbol or layout type.'}</p>}
    {product && <div><p className="workspace-product-name">{product.name}</p><p className="workspace-product-price">Catalog price · {money(product)} / {product.unit}</p></div>}
    {!device && singleWire && <label className="studio-field" data-workspace-field="conductors">Default individual wires per path<input type="number" min="1" max="1000" step="1" required value={count} onChange={e=>{setCount(e.target.value);setCountEdited(true)}}/><small>{assumedCount?'Estimated default filled in. ':''}This counts separate wires, not metres. A 10 m path with 3 wires needs 30 m of wire. Changing this sets the count for this connected network.</small></label>}
    {!device && product && !singleWire && <small>This is a complete cable. Its internal wires or pairs do not multiply the measured cable length.</small>}
    {!device && product && product.unit!=='meter' && (!(product.meters_per_unit || rule?.wire_meters_per_unit) || focusField==='wire-length') && <label className="studio-field" data-workspace-field="wire-length">Metres in one {product.unit}<input type="number" min="0.0001" max="100000" step="any" required value={length || product.meters_per_unit || rule?.wire_meters_per_unit || ''} onChange={e=>setLength(e.target.value)} placeholder="Length printed on the pack"/><small>Enter the length supplied in one purchased pack, not the total path length.</small></label>}
    {!device && <><label className="studio-field" data-workspace-field="conduit">Protective conduit<ConduitProductInput products={conduits} value={displayedConduit} disabled={!rule} onChange={id=>{setConduit(id);setConduitLength('')}}/></label>{conduitProduct && conduitProduct.unit!=='meter' && (!conduitPackLength || focusField==='conduit-length') && <label className="studio-field" data-workspace-field="conduit-length">Metres in one conduit {conduitProduct.unit}<input type="number" min="0.0001" max="100000" step="any" required value={conduitLength || conduitPackLength || ''} onChange={e=>setConduitLength(e.target.value)}/><small>The length of one purchased pipe or tubing piece.</small></label>}{!rule && <p role="status">Choose wiring with an Admin-approved conduit pair.</p>}{rule?.assumed && <small>Estimated pairing · editable by Admin</small>}</>}
    <WorkspaceGuide section={device?'device':'wiring'}/>
    {error && <p role="alert">{error}</p>}<footer className="account-actions"><Button type="button" variant="outline" disabled={busy} onClick={onClose}>Cancel</Button>{current && <Button type="button" variant="outline" disabled={busy} onClick={e=>save(e,true)}>Use plan default</Button>}<Button disabled={busy || !product || (!device && !displayedConduit)}>{busy?'Applying…':'Apply product'}</Button></footer>
  </form>
}
