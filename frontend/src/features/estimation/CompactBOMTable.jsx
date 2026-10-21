import { groupBOMRows } from './bomPricingRows.js'
import { orderNamed } from '../../utils/listOrder.js'
import { legendDescription } from '../../api/legendChoices.js'

const money=(value,currency)=>value==null ? '—' : new Intl.NumberFormat(undefined,{style:'currency',currency}).format(Number(value))
const label=row=>row.material_kind==='wire' ? 'Wire/cable' : 'Conduit'

export function CompactBOMTable({planning}) {
  // Totals and grouped quantities come from the server; the legacy fallback
  // only renders existing rows during a staggered deployment, never sums money.
  const groups=orderNamed(planning.display_groups ?? groupBOMRows(planning.items))
  return <div className="studio-table-scroll" role="region" aria-label="Draft material costs" tabIndex={0}>
    <table className="studio-estimate-table studio-bom-table bom-compact" aria-label="Draft bill of materials">
      <thead><tr><th>Device / wiring</th><th>Quantity</th><th>Unit price</th><th>Cost</th></tr></thead>
      <tbody>{groups.map(group=>{
        const members=group.members ?? group.components.flatMap(row=>(row.symbol_ids || row.path_ids || [row.path_id]).filter(Boolean).map(id=>({id,floor_plan_id:row.floor_plan_id,page_id:row.page_id})))
        return <tr key={group.key}>
          <td><strong>{legendDescription(group.name)}</strong>
            {members.length>0 && <select className="bom-reference-select" aria-label={`${group.kind==='device'?'Symbols':'Paths'} in ${legendDescription(group.name)}`} defaultValue="">
              <option value="" disabled>{members.length} {group.kind==='device'?'symbols':'paths'}</option>
              {members.map((member,index)=><option key={index} value={String(index)}>{member.id}{member.floor_plan_id ? ` · Plan ${member.floor_plan_id}`:''}{member.page_id ? ` · View ${member.page_id}`:''}</option>)}
            </select>}
            {group.components.map((row,index)=>(row.client_product_name || row.material_name) && <small key={index}>{group.kind==='path' ? `${label(row)} · `:''}{row.client_product_name || row.material_name}</small>)}
          </td>
          <td>{group.components.map((row,index)=><div className="bom-component" key={index}>{group.kind==='path' && <small>{label(row)}</small>}{row.unit==='source pixel' ? 'Unmeasured' : <>{new Intl.NumberFormat(undefined,{maximumFractionDigits:4}).format(Number(row.quantity))} {row.unit}</>}</div>)}</td>
          <td>{group.components.map((row,index)=><div className="bom-component" key={index}>{group.kind==='path' && <small>{label(row)}</small>}{money(row.unit_price ?? row.client_unit_price,row.currency)}{row.unit_price==null && row.client_unit_price!=null ? ` / ${row.client_price_unit}`:''}</div>)}</td>
          <td>{group.costs ? Object.keys(group.costs).length ? <>{Object.entries(group.costs).map(([currency,total])=><div key={currency}>{money(total,currency)}</div>)}{group.incomplete && <small>Partial</small>}</> : '—'
            : group.components.map((row,index)=><div key={index}>{money(row.line_total,row.currency)}</div>)}</td>
        </tr>
      })}</tbody>
      <tfoot>{planning.cost_summary && Object.keys(planning.cost_summary.currencies).length ? Object.entries(planning.cost_summary.currencies).map(([currency,amounts])=><TotalRows key={currency} currency={currency} amounts={amounts} partial={planning.cost_summary.incomplete}/>) : Object.keys(planning.priced_subtotals || {}).length ? Object.entries(planning.priced_subtotals).map(([currency,total])=><tr key={currency}><th scope="row" colSpan={3}>{planning.unpriced_items>0 ? 'Priced subtotal':'Total'} ({currency})</th><td>{money(total,currency)}</td></tr>)
        : <tr><th scope="row" colSpan={3}>Total</th><td>—</td></tr>}</tfoot>
    </table>
    {!groups.length && <p>No devices or wiring yet.</p>}
  </div>
}

function TotalRows({currency,amounts,partial}) {
  return <>
    {[['devices','Devices subtotal'],['conduit','Conduit subtotal'],['wire','Wire/cable subtotal']].map(([key,label])=><tr key={key} className="bom-subtotal"><th scope="row" colSpan={3}>{label} ({currency})</th><td>{money(amounts[key],currency)}</td></tr>)}
    <tr><th scope="row" colSpan={3}>Total so far ({currency}){partial && <small>Partial</small>}</th><td>{money(amounts.total,currency)}</td></tr>
  </>
}
