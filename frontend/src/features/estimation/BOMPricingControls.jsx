import { Button } from '../../components/ui/button.jsx'
import './clientPricing.css'

export function BOMPricingControls({model:m}) {
  const result=m.result,skipped=result ? [...result.skipped_rows,...result.skipped] : []
  return <div className="bom-pricing-controls">
    <p>Upload the client’s prices to automatically price compatible devices and wiring paths on {m.scopeLabel}. Wire/cable and conduit are priced separately. No VED price matching.</p>
    {m.busy && <p role="status">Applying client prices…</p>}
    {m.error && <p role="alert">{m.error}</p>}
    {m.uncertain && <Button disabled={m.busy} onClick={m.retry}>Retry upload</Button>}
    {result && <p role="status">{result.applied ? `Client prices applied to ${result.applied} device/wiring components.`:'No prices applied.'}{skipped.length ? ` ${skipped.length} rows or items could not be matched.`:''}</p>}
    {skipped.length>0 && <details><summary>Unmatched items ({skipped.length})</summary><ul>{skipped.map((row,index)=><li key={index}>{row.name}: {row.reason}</li>)}</ul></details>}
  </div>
}
