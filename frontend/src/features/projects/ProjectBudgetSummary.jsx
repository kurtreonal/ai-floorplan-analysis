const money=value=>new Intl.NumberFormat(undefined,{style:'currency',currency:'PHP'}).format(Number(value))

export function ProjectBudgetSummary({comparison}){
  if(!comparison)return null
  return <section className="project-budget-summary" aria-label="Budget comparison"><div><small>Allocated budget</small><strong>{money(comparison.allocated_budget)}</strong></div><div><small>{comparison.incomplete?'Priced subtotal':'Estimated cost'}</small><strong>{comparison.estimated_total==null?(comparison.status==='currency_mismatch'?'Estimate uses another currency':'Awaiting estimate'):money(comparison.estimated_total)}</strong></div>{comparison.estimated_total!=null && <div><small>{comparison.status==='over_budget'?'Over budget by':comparison.incomplete?'Remaining against priced subtotal':'Remaining budget'}</small><strong>{money(comparison.status==='over_budget'?comparison.over_budget:comparison.remaining)}</strong></div>}{comparison.incomplete && <small>Comparison covers priced items so far.</small>}</section>
}
