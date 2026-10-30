import { groupBOMRows } from './bomPricingRows.js'
import { orderNamed } from '../../utils/listOrder.js'
import { legendDescription } from '../../api/legendChoices.js'
import { Fragment,useState } from 'react'
import {getDemoInterpretationHref,getProjectHref,getLayoutHref} from '../../routes/projectRoutes.js'

const money=(value,currency)=>value==null ? '—' : new Intl.NumberFormat(undefined,currency ? {style:'currency',currency}:{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(value))
const label=row=>row.material_kind==='wire' ? 'Wire/cable' : 'Conduit'

export function CompactBOMTable({planning,onUseRuler,onEditScale,onEditMaterials,planScope}) {
  const [selection, setSelection] = useState({})
  // Totals and grouped quantities come from the server; the legacy fallback
  // only renders existing rows during a staggered deployment, never sums money.
  const labels={lighting:'Lighting layout',power:'Power layout',data:'Data layout'}
  const rank={lighting:0,power:1,data:2}
  const groups=orderNamed(planning.display_groups ?? groupBOMRows(planning.items)).sort((a,b)=>(rank[a.layout_category]??3)-(rank[b.layout_category]??3))
  const needsView=row=>planning.sources?.some(source=>source.floor_plan_id===row.floor_plan_id && source.page_id===row.page_id && source.scale_reason==='select_one_scaled_plan_view')
  return <div className="studio-table-scroll" role="region" aria-label="Draft material costs" tabIndex={0}>
    <table className="studio-estimate-table studio-bom-table bom-compact" aria-label="Draft bill of materials">
      <thead><tr><th>Device / wiring</th><th>Quantity</th><th>Unit price</th><th>Cost</th></tr></thead>
      <tbody>{groups.map((group,groupIndex)=>{
        const members=group.members ?? group.components.flatMap(row=>(row.symbol_ids || row.path_ids || [row.path_id]).filter(Boolean).map(id=>({id,floor_plan_id:row.floor_plan_id,page_id:row.page_id})))
        const selectedMember = selection[group.key] == null ? null : members[Number(selection[group.key])]
        return <Fragment key={group.key}>{(groupIndex===0 || groups[groupIndex-1].layout_category!==group.layout_category) && <tr className="bom-layout-heading"><th colSpan={4}>{labels[group.layout_category] || 'Layout not set'}</th></tr>}<tr>
          <td><strong>{legendDescription(group.name)}</strong>
            {members.length>0 && <select className="bom-reference-select" aria-label={`${group.kind==='device'?'Symbols':'Paths'} in ${legendDescription(group.name)}`} value={selection[group.key] ?? ''} onChange={e => setSelection(current => ({ ...current, [group.key]: e.target.value || null }))}>
              <option value="">All {members.length} {group.kind==='device'?'symbols':'paths'}</option>
              {members.map((member,index)=><option key={index} value={String(index)}>{group.kind === 'path' ? `Path ${index + 1}` : member.id}{member.measurement?.total_meters != null ? ` · ${Number(member.measurement.total_meters).toFixed(2)} m` : ''}{member.floor_plan_id ? ` · Plan ${member.floor_plan_id}`:''}</option>)}
            </select>}
            {group.kind === 'path' && <small>{selectedMember ? selectedMember.measurement?.total_meters != null ? `Selected path: ${Number(selectedMember.measurement.total_meters).toFixed(2)} m${selectedMember.measurement.incomplete ? ' · horizontal/known spans only' : ''}` : 'This path needs a measurement reference.' : 'Quantity shown is the total for all paths in this group.'}</small>}
            {group.kind === 'path' && selectedMember && members.length > 1 && <small>Shared spans and drops are counted once in the group total.</small>}
            {group.components.some(row=>row.connection_assumed) && <small>Uses existing route and default connection heights.</small>}
            {group.components.map((row,index)=>(row.client_product_name || row.material_name) && <small key={index}>{group.kind==='path' ? `${label(row)} · `:''}{!row.client_product_name && row.brand && !row.material_name?.toLowerCase().includes(row.brand.toLowerCase()) ? row.brand+' · ':''}{row.client_product_name || row.material_name}</small>)}
            {onEditMaterials && <WorkspaceProductLink group={group} planning={planning} member={selectedMember || members[0]}/>}
          </td>
          <td>{group.components.map((row,index)=><div className="bom-component" key={index}>{group.kind==='path' && <small>{label(row)}</small>}{row.unit==='source pixel'
            ? <MeasurementLinks row={row} planning={planning} members={members} selected={selectedMember} onEditScale={onEditScale} onUseRuler={onUseRuler} action={row.electrical_assignment_required?'wiring':needsView(row)?'view':'scale'}/>
            : <>{row.shared_purchase && Number(row.quantity)===0 ? 'Included in shared purchase':`${new Intl.NumberFormat(undefined,{maximumFractionDigits:4}).format(Number(row.quantity))} ${row.unit}`}{row.measured_meters != null && (row.unit !== 'meter' || row.purchase_increment_meters) && <small>{Number(row.measured_meters).toFixed(2)} m needed · {row.purchase_increment_meters ? `order in ${row.purchase_increment_meters} m lengths`:`${row.purchase_meters_per_unit} m / ${row.unit}`}</small>}
              {row.shared_purchase && Number(row.quantity)>0 && Number(row.shared_purchase_meters)>Number(row.measured_meters)+.01 && <small>Purchase covers {Number(row.shared_purchase_meters).toFixed(2)} m on this floor.</small>}
              {index===0 && row.missing_vertical_inputs?.length>0 && <MeasurementLinks row={row} planning={planning} members={members} selected={selectedMember} onEditScale={onEditScale} action="heights"/>}
            </>}</div>)}</td>
          <td>{group.components.map((row,index)=><div className="bom-component" key={index}>{group.kind==='path' && <small>{label(row)}</small>}{money(row.unit_price ?? row.client_unit_price ?? row.catalog_unit_price,row.unit_price!=null || row.client_unit_price!=null ? row.currency:row.catalog_currency)}{row.unit_price==null ? ` ${row.client_unit_price!=null ? '/ '+row.client_price_unit:row.catalog_unit_price!=null ? '/ '+row.catalog_price_unit:''}`:''}
            <PurchaseInputFix row={row} planning={planning} members={members} selected={selectedMember} onEditMaterials={onEditMaterials} planScope={planScope}/>
          </div>)}</td>
          <td>{group.costs ? Object.keys(group.costs).length ? <>{Object.entries(group.costs).map(([currency,total])=><div key={currency}>{money(total,currency)}</div>)}{group.purchase_cost_shared && <small>Share of purchase</small>}{group.incomplete && <small>Partial</small>}</> : '—'
            : group.components.map((row,index)=><div key={index}>{money(row.line_total,row.currency)}</div>)}</td>
        </tr></Fragment>
      })}</tbody>
      <tfoot>{planning.cost_summary && Object.keys(planning.cost_summary.currencies).length ? Object.entries(planning.cost_summary.currencies).map(([currency,amounts])=><TotalRows key={currency} currency={currency} amounts={amounts} partial={planning.cost_summary.incomplete} estimated={planning.cost_summary.estimated}/>) : Object.keys(planning.priced_subtotals || {}).length ? Object.entries(planning.priced_subtotals).map(([currency,total])=><tr key={currency}><th scope="row" colSpan={3}>{planning.unpriced_items>0 ? 'Priced subtotal':'Total'} ({currency})</th><td>{money(total,currency)}</td></tr>)
        : planning.cost_summary?.known_costs_without_currency ? <TotalRows amounts={planning.cost_summary.known_costs_without_currency} partial={planning.cost_summary.incomplete} estimated={planning.cost_summary.estimated}/>
          : <tr><th scope="row" colSpan={3}>Total</th><td>—</td></tr>}</tfoot>
    </table>
    {!groups.length && <p>No devices or wiring yet.</p>}
  </div>
}

function WorkspaceProductLink({group,planning,member,text,field}) {
  const source=planning.sources?.find(s=>s.floor_plan_id===member?.floor_plan_id && (!member?.page_id || s.page_id===member.page_id) && (!member?.candidate_run_id || member.candidate_run_id===s.candidate_run_id) && s.processing_job_id)
  return source && member?.id ? <a className="bom-inline-action" onClick={event=>{if(!event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey)requestAnimationFrame(()=>document.querySelector('.studio-review-page .studio-viewport-frame')?.scrollIntoView({block:'start'}))}} href={getDemoInterpretationHref(planning.project_id,source.floor_id,source.floor_plan_id,source.processing_job_id)+'?measure=product'+(field?'-'+field:'')+'&target='+encodeURIComponent(member.id)}>{text || `Edit ${group.kind==='device'?'device':'wiring'} in workspace`}</a>:null
}

function MeasurementLinks({row,planning,members,selected,onEditScale,onUseRuler,action:requestedAction}) {
  const issues=(row.measurement_issues || []).filter(issue=>!selected || issue.path_id===selected.id)
  const repair=requestedAction==='heights' ? issues.find(issue=>issue.kind==='wire-height') || issues.find(issue=>issue.kind==='device-height'):null
  const action=repair?.kind || (requestedAction==='heights' && selected?'wire-height':requestedAction)
  const unresolved=row.unresolved_path_ids || []
  const connectionTarget=selected && unresolved.includes(selected.id) ? selected.id:unresolved[0] || row.measurement_issues?.find(issue=>issue.kind==='wiring')?.path_id
  const target=action==='device-height'?repair?.symbol_id:action==='wiring'?connectionTarget || selected?.id || row.path_ids?.[0] || row.path_id:repair?.path_id || selected?.id || row.path_ids?.[0] || row.path_id
  const labels={view:'Choose plan area',scale:'Set measurements',wiring:'Check this wire’s connections',heights:'Set route / device heights',
    'wire-height':row.installation_method==='concealed_under_floor'?'Set depth below floor':'Set wire height','device-height':'Set device height',
    'material-wire':'Choose wire product','material-wire-length':'Enter metres per roll','material-conduit-length':'Enter metres per length','material-conductor-count':'Set conductor count'}
  const heightTargets=action==='wire-height' ? [...new Set((selected?[selected]:members).map(member=>member.id).filter(Boolean))]:[]
  if(heightTargets.length>1)labels['wire-height']=row.installation_method==='concealed_under_floor'?`Set depths for ${heightTargets.length} paths`:`Set heights for ${heightTargets.length} paths`
  if(onEditScale)return <button type="button" className="bom-use-ruler" onClick={()=>onEditScale(action,target,heightTargets)}>{labels[action]}</button>
  if(onUseRuler && action==='scale')return <button type="button" className="bom-use-ruler" onClick={onUseRuler}>{labels[action]}</button>
  const refs=selected?[selected]:members.length?members:[row]
  const sources=(planning.sources || []).filter(source=>refs.some(ref=>ref.floor_plan_id===source.floor_plan_id && (!ref.page_id || ref.page_id===source.page_id) && (!ref.candidate_run_id || ref.candidate_run_id===source.candidate_run_id)))
  const unique=[...new Map(sources.map(source=>[`${source.floor_plan_id}:${source.processing_job_id}`,source])).values()]
  const sourceTargets=source=>{
    const scoped=refs.filter(ref=>ref.floor_plan_id===source.floor_plan_id && (!ref.page_id || ref.page_id===source.page_id) && (!ref.candidate_run_id || ref.candidate_run_id===source.candidate_run_id))
    const chosen=action==='wire-height'?(scoped.find(ref=>ref.id===target)?.id || scoped[0]?.id || target):target
    return (chosen?'&target='+encodeURIComponent(chosen):'')+(action==='wire-height' && scoped.some(ref=>ref.id)?'&targets='+encodeURIComponent([...new Set(scoped.map(ref=>ref.id).filter(Boolean))].join(',')):'')
  }
  return <>{unique.map(source=><a key={`${source.floor_plan_id}:${source.processing_job_id}`} className="bom-use-ruler" href={source.processing_job_id ? getDemoInterpretationHref(planning.project_id,source.floor_id,source.floor_plan_id,source.processing_job_id)+'?measure='+(action==='scale' && source.scale_reason==='select_one_scaled_plan_view'?'view':action)+sourceTargets(source):getLayoutHref(planning.project_id,source.floor_id)}>{labels[action]}{unique.length>1?` · Plan ${source.floor_plan_id}`:''}</a>)}
    {!unique.length && planning.project_id && <a className="bom-use-ruler" href={getProjectHref(planning.project_id)}>Open plan workspace</a>}</>
}

function PurchaseInputFix({row,planning,members,selected,onEditMaterials,planScope}) {
  if(row.material_kind!=='wire' && row.material_kind!=='conduit')return null
  if(row.pricing_state==='conductor_count_required')return <WorkspaceProductLink group={{kind:'path'}} planning={planning} member={selected || members[0]} field="conductors" text="Set individual wire count"/>
  const product=planning.wire_materials?.find(m=>m.id===row.material_id)
  const missingRoll=row.material_kind==='wire' && product && product.unit!=='meter' && !(row.wire_meters_per_unit || row.purchase_meters_per_unit || product.meters_per_unit)
  const field=row.purchase_input_required || (missingRoll?'wire-length':row.material_kind==='wire' && !row.material_id && row.unit_price==null && row.client_unit_price==null?'wire-product':null)
  if(!field)return null
  const action=field==='wire-product'?'material-wire':field==='wire-length'?'material-wire-length':'material-conduit-length'
  const title=field==='wire-product'?'Choose wire product':field==='wire-length'?`Enter metres per ${product?.unit || 'roll'}`:'Enter metres per length'
  if((selected || members[0])?.id && planning.sources?.some(source=>source.floor_plan_id===(selected || members[0]).floor_plan_id && source.processing_job_id))return <WorkspaceProductLink group={{kind:'path'}} planning={planning} member={selected || members[0]} field={field==='wire-product'?'wire':field==='wire-length'?'wire-length':'conduit-length'} text={title}/>
  if(onEditMaterials && (planScope===row.floor_plan_id || !row.floor_plan_id))return <button type="button" className="bom-use-ruler" onClick={()=>onEditMaterials(field)}>{title}</button>
  return <MeasurementLinks row={row} planning={planning} members={members} selected={selected} action={action}/>
}

function TotalRows({currency,amounts,partial,estimated}) {
  return <>
    {[['devices','Devices subtotal'],['conduit','Conduit subtotal'],['wire','Wire/cable subtotal']].map(([key,label])=><tr key={key} className="bom-subtotal"><th scope="row" colSpan={3}>{label}{currency ? ` (${currency})`:''}</th><td>{money(amounts[key],currency)}</td></tr>)}
    <tr><th scope="row" colSpan={3}>{estimated ? 'Estimated total':'Total so far'}{currency ? ` (${currency})`:''}{partial && <small>Partial</small>}</th><td>{money(amounts.total,currency)}</td></tr>
  </>
}
