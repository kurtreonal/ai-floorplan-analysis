import { Button } from '../../components/ui/button.jsx'
import './clientPricing.css'

export function BOMPricingControls({model}) {
  const m=model,p=m.previewResult
  return <div className="bom-pricing-controls">
    {m.stage==='versions' && <label>Saved price list<select disabled={m.locked} defaultValue="" onChange={e=>m.chooseVersion(e.target.value)}><option value="" disabled>Choose an import</option>{m.versions.map(v=><option key={v.id} value={v.id}>{v.filename} · version {v.version_number}</option>)}</select></label>}
    {m.stage==='mapping' && <section aria-label="Imported pricing preview">
      <p>Review file prices and matches. Client quantities do not replace calculated quantities. This import will price selected existing items only.</p>
      <div className="client-price-table"><table><thead><tr><th>Include</th><th>Client product</th><th>Catalog match</th><th>Price / purchase unit</th><th>Catalog units per purchase</th><th>Review</th></tr></thead><tbody>
        {m.proposal.document.rows.map(row=><tr key={row.row_id}>
          <td><input aria-label={`Include ${row.row_id}`} type="checkbox" disabled={m.locked} checked={!row.excluded} onChange={e=>m.changeImport(row.row_id,{excluded:!e.target.checked})}/></td>
          <td>{row.name}<small>{row.code} {row.specification}</small><small>{row.client_quantity==null ? 'No client quantity':`Client quantity ${row.client_quantity} (reference only)`}</small></td>
          <td><select aria-label={`Catalog match ${row.row_id}`} disabled={m.locked || row.excluded} value={row.material_id || ''} onChange={e=>m.changeImport(row.row_id,{material_id:e.target.value ? Number(e.target.value):null})}>
            <option value="">Resolve match</option>{m.proposal.materials.map(product=><option key={product.id} value={product.id}>{product.code} · {product.name} / {product.unit}</option>)}
          </select></td><td>{row.currency} {row.unit_price??'Missing price'} / {row.unit}</td>
          <td><input aria-label={`Conversion ${row.row_id}`} type="number" disabled={m.locked || row.excluded} min="0.0001" max="100000" step="any" value={row.units_per_purchase??''} onChange={e=>m.changeImport(row.row_id,{units_per_purchase:e.target.value || null})}/></td>
          <td>{row.excluded ? 'Excluded':row.reasons.join(' ') || 'Matched'}</td>
        </tr>)}
      </tbody></table></div>
      <Button variant="outline" disabled={m.locked} onClick={m.reviewImport}>Check mappings</Button>
      <Button disabled={m.locked || !m.proposal.ready} onClick={m.acceptImport}>Use imported prices</Button>
    </section>}
    {m.active && <>
      <div className="item-price-controls">
        <label>Search BOM items<input type="search" value={m.query} disabled={m.locked} onChange={e=>m.update({query:e.target.value})}/></label>
        <label>Item type<select value={m.type} disabled={m.locked} onChange={e=>m.update({type:e.target.value})}><option value="">All</option><option value="device">Devices</option><option value="path">Wiring paths</option></select></label>
        <label>Apply scope<select value={m.scope} disabled={m.locked} onChange={e=>m.update({scope:e.target.value,selected:[]})}><option value="project">Entire project</option>{m.inventory.floors.map(id=><option key={id} value={`floor:${id}`}>Floor {id}</option>)}</select></label>
      </div>
      <div className="item-price-actions">
        <Button variant="outline" disabled={m.locked || !m.groups.length} onClick={m.selectVisible}>Select visible results</Button>
        <Button variant="outline" disabled={m.locked || !m.selected.length} onClick={m.clear}>Clear selection</Button>
        <Button disabled={m.locked || !m.selected.length} onClick={()=>m.requestPreview()}>Preview selected ({m.selected.length})</Button>
        <Button variant="outline" disabled={m.locked || !m.inventory.items.some(r=>r.kind==='path')} onClick={()=>m.requestPreview(true)}>Preview all compatible existing wiring paths</Button>
      </div>
      {p && <section aria-label="Price application preview"><p>{p.affected.length} compatible material assignments; {p.skipped.length} skipped. Scope: {m.scopeFloor ? `Floor ${m.scopeFloor}`:'Entire project'}. New items are not included.</p>
        {p.skipped.length>0 && <details><summary>Skipped matches ({p.skipped.length})</summary><ul>{p.skipped.map(row=><li key={row.item_key}>{row.name}: {row.reason}</li>)}</ul></details>}
        <Button disabled={m.locked || !p.ready} onClick={m.apply}>Apply prices to {p.affected.length} items</Button>
      </section>}
    </>}
    {m.stage!=='idle' && <div className="item-price-actions"><Button variant="outline" disabled={m.busy || m.uncertain} onClick={m.finish}>Finish pricing</Button><Button variant="ghost" disabled={m.busy || m.uncertain} onClick={m.finish}>Cancel pricing</Button></div>}
    {m.uncertain && <Button disabled={m.busy} onClick={m.retry}>Retry identical price request</Button>}
    {m.busy && <p role="status">Updating pricing…</p>}{m.error && <p role="alert">{m.error}</p>}{m.message && <p role="status">{m.message}</p>}
  </div>
}
