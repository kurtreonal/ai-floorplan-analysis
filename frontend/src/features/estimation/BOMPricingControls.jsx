import { Button } from '../../components/ui/button.jsx'
import './clientPricing.css'

export function BOMPricingControls({model:m}) {
  const result=m.result,skipped=result ? [...result.skipped_rows,...result.skipped] : []
  return <div className="bom-pricing-controls">
    {m.busy && <p role="status">Applying client prices…</p>}
    {m.error && <p role="alert">{m.error}</p>}
    {m.uncertain && <Button disabled={m.busy} onClick={m.retry}>Retry upload</Button>}
    {result && <p role="status">{result.applied ? `Client prices applied to ${result.applied} device/wiring components.`:'No prices applied.'}{skipped.length ? ` ${skipped.length} rows or items could not be matched.`:''}</p>}
  </div>
}
