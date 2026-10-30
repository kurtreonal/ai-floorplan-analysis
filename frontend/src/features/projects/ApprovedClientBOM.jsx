import {ProjectBudgetSummary} from './ProjectBudgetSummary.jsx'
const money=(value,currency)=>value==null?'Not priced':new Intl.NumberFormat(undefined,{style:'currency',currency:currency || 'PHP'}).format(Number(value))

export function ApprovedClientBOM({estimate}){
  const totals=estimate.totals || (estimate.currency && estimate.total!=null?{[estimate.currency]:estimate.total}:{})
  return <section className="workflow-panel"><h2>{estimate.kind==='approved_bom'?'Approved project BOM':'Approved estimate'}</h2>
    <ProjectBudgetSummary comparison={estimate.budget_comparison}/>
    <p>{estimate.estimated?'Estimated total':'Captured quantities and prices'}{estimate.incomplete?' · Some items need measurements or prices.':''}</p>
    <div className="studio-table-scroll"><table className="studio-project-table"><thead><tr><th>Category</th><th>Product / brand</th><th>Quantity</th><th>Unit price</th><th>Cost</th></tr></thead><tbody>{estimate.items.map((item,index)=>{
      const shared=Number(item.quantity)===0 && item.cost!=null && Number(item.cost)===0
      return <tr key={index}><td>{item.category || 'Material'}</td><th scope="row">{item.name}{item.brand && <small>{item.brand}</small>}{item.item_number && <small>{item.item_number}</small>}</th><td>{item.quantity==null?'Not measured':shared?'—':`${item.quantity} ${item.unit}`}</td><td>{money(item.unit_price,item.currency || estimate.currency)}</td><td>{shared?'Included in shared purchase':money(item.cost,item.currency || estimate.currency)}</td></tr>
    })}</tbody><tfoot>{Object.entries(totals).map(([currency,total])=><tr key={currency}><th colSpan={4}>{estimate.incomplete?'Priced subtotal':estimate.estimated?'Estimated total':'Total'} ({currency})</th><td>{money(total,currency)}</td></tr>)}{!Object.keys(totals).length && <tr><th colSpan={4}>Total</th><td>Not priced yet</td></tr>}</tfoot></table></div>
  </section>
}
