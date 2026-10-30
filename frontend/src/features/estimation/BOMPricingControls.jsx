import { Button } from '../../components/ui/button.jsx'
import './clientPricing.css'

export function BOMPricingControls({model:m}) {
  const result=m.result,skipped=result ? [...result.skipped_rows,...result.skipped] : []
  return <div className="bom-pricing-controls">
    {!!m.imports?.length && <div className="client-pricing-source"><span>{m.imports.length} uploaded price {m.imports.length===1?'list':'lists'}</span><Button variant="ghost" disabled={m.locked} onClick={m.remove}>Remove client pricing</Button></div>}
    {m.busy && <p role="status">Applying client prices…</p>}
    {m.error && <p role="alert">{m.error}</p>}
    {m.uncertain && <Button disabled={m.busy} onClick={m.retry}>Retry upload</Button>}
    {result && <p role="status">{result.applied ? `Client prices applied to ${result.applied} device/wiring components.`:'No prices applied.'}{skipped.length ? ` ${skipped.length} rows or items could not be matched.`:''}</p>}
  </div>
}
