import {ProjectBudgetSummary} from '../projects/ProjectBudgetSummary.jsx'
import {layoutValues} from '../projects/projectIntake.js'
import { useEffect, useRef, useState } from 'react'
import { fetchBOM, downloadBOM, downloadDraftBOM } from '../../api/bom.js'
import { Button } from '../../components/ui/button.jsx'
import { orderList } from '../../utils/listOrder.js'
import { useBOMPricing } from './useBOMPricing.js'
import { BOMPricingControls } from './BOMPricingControls.jsx'
import { BOMTable } from './BOMTable.jsx'
import {LAYOUT_TYPES} from '../projects/projectIntake.js'

const pricingLabels = {
  compatible_conduit_required:'Admin must configure a compatible wire / conduit pair',
  item_price_review_required:'Client specification changed; upload an updated BOM',
  electrical_assignment_required:'Electrical assignment required',
  measurement_incomplete:'Complete route measurements required',
  conductor_count_required:'Set conductor count for this single-core wire',
  scale_required: 'Set plan scale once', classification_required: 'Unclassified',
  material_not_found: 'Upload client BOM pricing', ambiguous_material: 'Product specification is ambiguous',
  purchase_unit_required: 'Purchase-unit conversion needed', missing_price: 'Price missing', priced: 'Priced',
  missing_project_material_price: 'Not priced in client import',
  project_material_identity_changed: 'Material changed; review client mapping',
  network_material_review_required: 'Review overlapping path materials',
}

export function BOMPanel({ projectId, floorPlanId, processingJobId, estimate, refreshKey = 0, draftPreview = null, designer = false, unsaved = false, onPriceVersionsChange, onPricesApplied, onUseRuler, onEditScale,onBOMChange,onEditWorkspaceMaterials }) {
  const [loadedBOM, setBOM] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pricingRevision, setPricingRevision] = useState(0)
  const pricingFile = useRef(null)
  const download = useRef(null)
  const sourceKey = `${projectId}:${floorPlanId || ''}:${processingJobId || ''}`
  function openMaterialEditor(field){
    if(onEditWorkspaceMaterials){onEditWorkspaceMaterials(field);return}
    const source=planningOptions?.sources?.find(s=>s.processing_job_id)
    if(source)window.location.assign(`#/app/projects/${projectId}/floors/${source.floor_id}/floor-plans/${source.floor_plan_id}/interpretation/${source.processing_job_id}?measure=${field==='conductor-count'?'material-conductor-count':field==='wire-length'?'material-wire-length':field==='conduit-length'?'material-conduit-length':'material-wire'}`)
  }
  const chosen={}
  const calculatorKey=JSON.stringify(chosen)
  const calculatorOptions={
    conduitMaterialId:chosen.conduit ? Number(chosen.conduit):undefined,
    wireMaterialId:chosen.wire ? Number(chosen.wire):undefined,wireMetersPerUnit:chosen.wire ? chosen.wireMetersPerUnit:undefined,
    conduitPricePerMeter:chosen.conduitPricePerMeter,wirePricePerMeter:chosen.wirePricePerMeter,
    purchasePricing:chosen.purchasePricing,
    paperSize:chosen.paper,customWidthMm:chosen.paper==='CUSTOM' ? chosen.customWidthMm:undefined,
    customHeightMm:chosen.paper==='CUSTOM' ? chosen.customHeightMm:undefined,scaleDenominator:chosen.scaleDenominator,deviceMaterials:chosen.deviceMaterials}
  const previewKey = draftPreview ? JSON.stringify(draftPreview) : ''
  const livePreview = Boolean(previewKey)
  const scopeKey = `${sourceKey}:${refreshKey}:${pricingRevision}:${previewKey}:${calculatorKey}`
  const bom = loadedBOM?.scopeKey === scopeKey ? loadedBOM.value : null
  useEffect(()=>{onBOMChange?.(bom)},[bom,onBOMChange])
  const planningOptions = loadedBOM?.sourceKey === sourceKey ? loadedBOM.value?.planning : null
  const pricing = useBOMPricing({projectId,floorId:floorPlanId ? planningOptions?.sources?.[0]?.floor_id:undefined,disabled:busy || unsaved || !designer || !planningOptions || Boolean(floorPlanId && !planningOptions?.sources?.[0]?.floor_id),
    onVersionsChange:onPriceVersionsChange,onApplied:()=>{setPricingRevision(n=>n+1);onPricesApplied?.()}})
  useEffect(() => {
    const controller = new AbortController()
    const options=JSON.parse(calculatorKey)
    const timer = setTimeout(() => fetchBOM(projectId, { signal: controller.signal, floorPlanId, processingJobId,
      conduitMaterialId:options.conduit ? Number(options.conduit):undefined,
      wireMaterialId:options.wire ? Number(options.wire):undefined,
      wireMetersPerUnit:options.wire ? options.wireMetersPerUnit:undefined,wirePricePerMeter:options.wirePricePerMeter,
      conduitPricePerMeter:options.conduitPricePerMeter,paperSize:options.paper,
      purchasePricing:options.purchasePricing,
      customWidthMm:options.paper==='CUSTOM'?options.customWidthMm:undefined,customHeightMm:options.paper==='CUSTOM'?options.customHeightMm:undefined,
      scaleDenominator:options.scaleDenominator,deviceMaterials:options.deviceMaterials,draftPreview:previewKey ? JSON.parse(previewKey) : null }).then((value) => { if (!controller.signal.aborted) { setBOM({scopeKey,sourceKey,value}); setError('') } })
      .catch((failure) => { if (!controller.signal.aborted) { setBOM(null); setError(failure.message) } })
    , livePreview ? 350 : 0)
    return () => { clearTimeout(timer); controller.abort() }
  }, [projectId, floorPlanId, processingJobId, refreshKey, scopeKey, sourceKey,previewKey,livePreview,calculatorKey])
  useEffect(() => () => download.current?.abort(), [])
  async function exportSnapshot(draft = false) {
    if ((!draft && !estimate) || busy) return
    const controller = new AbortController(); download.current = controller
    setBusy(true)
    try {
      const blob = draft ? await downloadDraftBOM(projectId, { signal: controller.signal, floorPlanId, processingJobId, draftPreview,...calculatorOptions })
        : await downloadBOM(projectId, estimate.id, { signal: controller.signal })
      if (controller.signal.aborted) return
      const url = URL.createObjectURL(blob), link = document.createElement('a')
      link.href = url; link.download = draft ? `VED-Bill-of-Materials-${projectId}.xlsx` : `VED-Bill-of-Materials-${projectId}-v${estimate.version_number}.xlsx`; link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (failure) { if (!controller.signal.aborted) setError(failure.message) }
    finally { if (!controller.signal.aborted) setBusy(false) }
  }
  return <section className="studio-panel studio-bom-panel" aria-labelledby="bom-title"><div className="studio-panel-heading"><h2 id="bom-title">Bill of materials</h2>
    <div>{onEditScale && <Button variant="outline" onClick={()=>onEditScale('scale')}>Plan measurements</Button>}{designer && <><input ref={pricingFile} className="sr-only" aria-label="Upload client BOM file" type="file" accept=".xlsx,.csv" disabled={pricing.locked} onChange={event=>{pricing.uploaded(event.target.files?.[0]);event.target.value=''}}/>
      <Button variant="outline" disabled={pricing.locked} onClick={()=>pricingFile.current?.click()}>Upload BOM</Button>
      </>}
    {designer && <Button variant="outline" disabled={!planningOptions} onClick={()=>openMaterialEditor('wire-product')}>Material settings in workspace</Button>}
    <Button variant="ghost" disabled={busy} onClick={()=>setPricingRevision(n=>n+1)}>Refresh BOM</Button>
    <Button variant="outline" disabled={!bom?.planning || busy} onClick={() => exportSnapshot(true)}>Download BOM</Button>
    {!floorPlanId && <Button variant="outline" disabled={!estimate || busy} onClick={() => exportSnapshot()}>{busy ? 'Downloading…' : 'Download estimate BOM'}</Button>}</div></div>
    {planningOptions && <div className="bom-layout-choice"><strong>{layoutValues(planningOptions.layout_type).map(type=>LAYOUT_TYPES.find(([key])=>key===type)?.[1]).filter(Boolean).join(' / ') || 'Layout type not set'}</strong><small>Material choices follow the layout selected before analysis. Change it in the saved floor plan’s Options.</small></div>}
    {unsaved && <p role="status">{draftPreview ? 'Live draft quantities; saved estimate snapshots are unchanged.' : 'Unsaved changes: this BOM shows saved items. Save to refresh quantities.'}</p>}
    {designer && <BOMPricingControls model={pricing}/>}
    {bom?.planning && <>
      {bom.planning.items.length || pricing.active ? <BOMTable planning={bom.planning} pricing={pricing} pricingLabels={pricingLabels} onUseRuler={onUseRuler} onEditScale={onEditScale} onEditMaterials={designer ? openMaterialEditor:undefined} planScope={floorPlanId}/> : <p>No saved devices or wiring yet.</p>}
      {bom.planning.cost_summary?.estimated
        ? <small className="bom-compact-warning" role="note">Estimated from planning assumptions. Missing spans, heights or prices may make this total partial.</small>
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
    <ProjectBudgetSummary comparison={bom?.planning?.budget_comparison}/>
    {error && <p role="alert">{error}</p>}
    {draftPreview && !bom && !error && <p role="status">Updating takeoff from the canvas…</p>}
    {estimate && <p>Download uses estimate version {estimate.version_number}, including its captured prices and additional materials—not today’s price list.</p>}
  </section>
}
