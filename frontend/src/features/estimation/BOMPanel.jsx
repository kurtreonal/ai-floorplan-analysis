import { useEffect, useRef, useState } from 'react'
import { fetchBOM, downloadBOM, downloadDraftBOM } from '../../api/bom.js'
import { Button } from '../../components/ui/button.jsx'
import { orderList } from '../../utils/listOrder.js'
import { useBOMPricing } from './useBOMPricing.js'
import { BOMPricingControls } from './BOMPricingControls.jsx'
import { BOMTable } from './BOMTable.jsx'
import { IndividualPriceEditor } from './IndividualPriceEditor.jsx'

const pricingLabels = {
  item_price_review_required:'Client specification changed; upload an updated BOM',
  electrical_assignment_required:'Electrical assignment required',
  measurement_incomplete:'Complete route measurements required',
  network_material_review_required: 'Review overlapping path materials',
  scale_required: 'Set plan scale once', classification_required: 'Unclassified',
  material_not_found: 'Upload client BOM pricing', ambiguous_material: 'Product specification is ambiguous',
  purchase_unit_required: 'Purchase-unit conversion needed', missing_price: 'Price missing', priced: 'Priced',
  missing_project_material_price: 'Not priced in client import',
  project_material_identity_changed: 'Material changed; review client mapping',
}

export function BOMPanel({ projectId, floorPlanId, processingJobId, estimate, refreshKey = 0, designer = false, unsaved = false, onPriceVersionsChange, onPricesApplied }) {
  const [loadedBOM, setBOM] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pricingRevision, setPricingRevision] = useState(0)
  const pricingFile = useRef(null)
  const download = useRef(null)
  const sourceKey = `${projectId}:${floorPlanId || ''}:${processingJobId || ''}`
  const scopeKey = `${sourceKey}:${refreshKey}:${pricingRevision}`
  const bom = loadedBOM?.scopeKey === scopeKey ? loadedBOM.value : null
  const planningOptions = loadedBOM?.sourceKey === sourceKey ? loadedBOM.value?.planning : null
  const pricing = useBOMPricing({projectId,floorId:floorPlanId ? planningOptions?.sources?.[0]?.floor_id:undefined,disabled:busy || unsaved || !designer || !planningOptions || Boolean(floorPlanId && !planningOptions?.sources?.[0]?.floor_id),
    onVersionsChange:onPriceVersionsChange,onApplied:()=>{setPricingRevision(n=>n+1);onPricesApplied?.()}})
  useEffect(() => {
    const controller = new AbortController()
    fetchBOM(projectId, { signal: controller.signal, floorPlanId, processingJobId }).then((value) => { if (!controller.signal.aborted) { setBOM({scopeKey,sourceKey,value}); setError('') } })
      .catch((failure) => { if (!controller.signal.aborted) { setBOM(null); setError(failure.message) } })
    return () => controller.abort()
  }, [projectId, floorPlanId, processingJobId, refreshKey, scopeKey, sourceKey])
  useEffect(() => () => download.current?.abort(), [])
  async function exportSnapshot(draft = false) {
    if ((!draft && !estimate) || busy) return
    const controller = new AbortController(); download.current = controller
    setBusy(true)
    try {
      const blob = draft ? await downloadDraftBOM(projectId, { signal: controller.signal, floorPlanId, processingJobId })
        : await downloadBOM(projectId, estimate.id, { signal: controller.signal })
      if (controller.signal.aborted) return
      const url = URL.createObjectURL(blob), link = document.createElement('a')
      link.href = url; link.download = draft ? `ved-draft-bom-${projectId}.csv` : `ved-bom-${estimate.id}.csv`; link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (failure) { if (!controller.signal.aborted) setError(failure.message) }
    finally { if (!controller.signal.aborted) setBusy(false) }
  }
  return <section className="studio-panel studio-bom-panel" aria-labelledby="bom-title"><div className="studio-panel-heading"><h2 id="bom-title">Bill of materials</h2>
    <div>{designer && <><input ref={pricingFile} className="sr-only" aria-label="Upload client BOM file" type="file" accept=".xlsx,.csv" disabled={pricing.locked} onChange={event=>{pricing.uploaded(event.target.files?.[0]);event.target.value=''}}/>
      <Button variant="outline" disabled={pricing.locked} onClick={()=>pricingFile.current?.click()}>Upload BOM</Button>
      </>}
    {designer && <IndividualPriceEditor key={sourceKey} projectId={projectId} floorPlanId={floorPlanId} disabled={pricing.locked || !bom?.planning} onSaved={()=>{setPricingRevision(n=>n+1);onPricesApplied?.()}}/>}
    <Button variant="outline" disabled={!bom?.planning || busy} onClick={() => exportSnapshot(true)}>Download draft BOM</Button>
    {!floorPlanId && <Button variant="outline" disabled={!estimate || busy} onClick={() => exportSnapshot()}>{busy ? 'Downloading…' : 'Download saved BOM'}</Button>}</div></div>
    {unsaved && <p role="status">Unsaved changes: this BOM shows saved items. Save to refresh quantities.</p>}
    {designer && <BOMPricingControls model={pricing}/>}
    {bom?.planning && <>
      {bom.planning.items.length || pricing.active ? <BOMTable planning={bom.planning} pricing={pricing} pricingLabels={pricingLabels}/> : <p>No saved devices or wiring yet.</p>}
      {bom.planning.sources?.some(source=>source.scale_basis==='ved_paper_ratio_draft')
        ? <small className="bom-compact-warning" role="note">Draft paper scale is active. Unknown drops and unpriced items are excluded.</small>
        : (bom.planning.unpriced_items>0 || bom.planning.missing_inputs?.length>0) && <small className="bom-compact-warning" role="note">Some items need prices or measurements. Any subtotal is partial.</small>}
    </>}
    {bom && !bom.planning && <>
      <p>{bom.layouts.length} reviewed floor snapshots. Raw detections are excluded from quantities.</p>
      {bom.components.length > 0 ? <div className="studio-table-scroll"><table className="studio-estimate-table"><thead><tr><th>Floor</th><th>Reviewed device</th><th>Quantity</th></tr></thead>
        <tbody>{orderList(bom.components, row => row.floor_id, row => row.name).map((row) => <tr key={`${row.floor_id}:${row.class_id}`}><td>{row.floor_id}</td><td>{row.name}</td><td>{row.quantity}</td></tr>)}</tbody></table></div>
        : <p>No reviewed device quantities yet. Save a reviewed canonical layout to populate the BOM.</p>}
      <p>{bom.route_lengths ? `Measured conduit path: ${bom.route_lengths.conduit_meters} m.` : 'Wire and conduit quantities await a current measured route and conductor inputs.'}</p>
      {bom.wiring_types?.length > 0 && <div><h3>Drawing wiring types</h3>
        <ul>{orderList(bom.wiring_types, row => row.floor_plan_id, row => row.name).map(row => <li key={`${row.floor_plan_id}:${row.wiring_legend_id}`}>
          {row.name.replace(/ \[pdf-.*$/, '')} · Plan {row.floor_plan_id}
        </li>)}</ul>
        <p>Draft types only. Cable size, conductor count, measured lengths and material prices are still required for costing.</p>
      </div>}
      {bom.missing_layout_floors.length > 0 && <p role="note">Floors without reviewed layouts: {bom.missing_layout_floors.join(', ')}.</p>}
    </>}
    {error && <p role="alert">{error}</p>}
    {estimate && <p>Download uses estimate version {estimate.version_number}, including its captured prices and additional materials—not today’s price list.</p>}
  </section>
}
