import { groupBOMRows } from './bomPricingRows.js'
import { orderNamed } from '../../utils/listOrder.js'
import { legendDescription } from '../../api/legendChoices.js'

const money=(n,c)=>n==null ? '—':new Intl.NumberFormat(undefined,{style:'currency',currency:c}).format(Number(n))
const label=row=>row.kind==='device' ? 'Device':row.material_kind==='wire' ? 'Wire/cable':row.material_kind==='conduit' ? 'Conduit':'Path'
export function BOMTable({planning,pricing,pricingLabels}) {
  const active=pricing.active,groups=orderNamed(active ? pricing.groups:groupBOMRows(planning.items))
  const change=row=>pricing.previewResult?.affected.find(r=>r.item_key===row.item_key)
  return <div className="studio-table-scroll" role="region" aria-label="Draft material costs" tabIndex={0}><table className="studio-estimate-table studio-bom-table" aria-label="Draft bill of materials"><thead><tr>
    {active && <th>Select</th>}<th>Device / wiring</th><th>Quantity</th><th>{active ? 'Imported product / unit price':'Unit price'}</th><th>Cost / missing input</th>
  </tr></thead><tbody>{groups.map(group=><tr key={group.key}>
    {active && <td><input type="checkbox" aria-label={`Select ${group.name} ${group.key}`} disabled={pricing.locked} checked={pricing.selected.includes(group.key)} onChange={e=>pricing.toggle(group,e.target.checked)}/></td>}
    <td>{legendDescription(group.name)}{group.components.map((row,index)=><small key={index}>{label(row)}{row.client_product_name || row.material_name ? ` · ${row.client_product_name || row.material_name}`:''}{row.symbol_ids?.length ? ` · ${row.symbol_ids.join(', ')}`:''}</small>)}</td>
    <td>{group.components.map((row,index)=><div className="bom-component" key={index}><small>{label(row)}</small>{new Intl.NumberFormat(undefined,{maximumFractionDigits:4}).format(Number(row.quantity))} {row.unit}
      {row.vertical_meters>0 && <small>Includes {row.vertical_meters} m drop/rise</small>}
      {row.missing_vertical_inputs?.length>0 && <details><summary>{row.missing_vertical_inputs.every(n=>n.includes('connected drop/rise')) ? 'Connected · drop/rise inputs needed':'Drop/rise inputs needed'}</summary><ul>{row.missing_vertical_inputs.map(note=><li key={note}>{note}</li>)}</ul></details>}
    </div>)}</td>
    <td>{group.components.map((row,index)=><div className="bom-component" key={index}><small>{label(row)}</small>
      {active && <select aria-label={`Imported product ${row.item_key}`} disabled={pricing.locked} value={pricing.chosen(row)} onChange={e=>pricing.update({choices:{...pricing.choices,[row.item_key]:e.target.value}})}>
        <option value="">{row.material_id ? 'Choose compatible price':'Choose compatible product'}</option>{pricing.entries.filter(q=>row.compatible_prices ? row.compatible_prices.includes(q.row_id):q.material_id===row.material_id).map(q=><option key={q.row_id} value={q.row_id}>{q.name} · {money(q.unit_price,q.currency)} / {q.unit}</option>)}
      </select>}
      {change(row) ? <span>{money(change(row).previous_price,change(row).previous_currency)} → {money(change(row).unit_price,change(row).currency)} / {row.unit}</span>:row.unit_price==null && row.client_unit_price!=null ? <span>{money(row.client_unit_price,row.currency)} / {row.client_price_unit}</span>:money(row.unit_price,row.currency)}
    </div>)}</td>
    <td>{group.components.map((row,index)=><div className="bom-component" key={index}><small>{label(row)}</small>{change(row) ? change(row).line_total==null ? 'Measurements required before costing':<span>{money(change(row).previous_total,change(row).previous_currency)} → {money(change(row).line_total,change(row).currency)}</span>:row.line_total==null ? pricingLabels[row.pricing_state] || 'Not priced':money(row.line_total,row.currency)}</div>)}</td>
  </tr>)}</tbody><tfoot>{Object.entries(planning.priced_subtotals).map(([currency,total])=><tr key={currency}><th scope="row" colSpan={active ? 4:3}>Current subtotal ({currency})</th><td>{money(total,currency)}</td></tr>)}</tfoot></table>{!groups.length && <p>No matching BOM items.</p>}</div>
}
