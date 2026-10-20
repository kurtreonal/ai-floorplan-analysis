import { useEffect, useRef, useState } from 'react'
import { fetchBOM, downloadBOM, downloadDraftBOM } from '../../api/bom.js'
import { Button } from '../../components/ui/button.jsx'
import { orderNamed, orderList } from '../../utils/listOrder.js'
import { useBOMPricing } from './useBOMPricing.js'
import { BOMPricingControls } from './BOMPricingControls.jsx'
import { BOMTable } from './BOMTable.jsx'

const pricingLabels = {
  item_price_review_required:'Review saved client price: material or unit changed',
  electrical_assignment_required:'Electrical assignment required',
  measurement_incomplete:'Complete route measurements required',
  network_material_review_required: 'Review overlapping path materials',
  scale_required: 'Set plan scale once', classification_required: 'Unclassified',
  material_not_found: 'No matching catalog material', ambiguous_material: 'Multiple matching materials',
  purchase_unit_required: 'Purchase-unit conversion needed', missing_price: 'Price missing', priced: 'Priced',
  missing_project_material_price: 'Not priced in client import',
  project_material_identity_changed: 'Material changed; review client mapping',
}
function money(value, currency) {
  return value == null ? '—' : new Intl.NumberFormat(undefined, {style:'currency',currency}).format(Number(value))
}

export function BOMPanel({ projectId, floorPlanId, processingJobId, estimate, refreshKey = 0, designer = false, unsaved = false, onPriceVersionsChange, onPricesApplied }) {
  const [loadedBOM, setBOM] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [calculation, setCalculation] = useState({})
  const [pricingRevision, setPricingRevision] = useState(0)
  const pricingFile = useRef(null)
  const download = useRef(null)
  const sourceKey = `${projectId}:${floorPlanId || ''}:${processingJobId || ''}`
  const chosen = calculation.sourceKey === sourceKey ? calculation : {}
  const conduitMaterialId = chosen.conduit ? Number(chosen.conduit) : undefined
  const wireMaterialId = chosen.wire ? Number(chosen.wire) : undefined
  const wireMetersPerUnit = chosen.wireMetersPerUnit
  const wirePricePerMeter = chosen.wirePricePerMeter
  const paperChoice = chosen.paper ?? (floorPlanId ? 'A3' : '')
  const customWidthMm = paperChoice === 'CUSTOM' ? chosen.custom?.width : undefined
  const customHeightMm = paperChoice === 'CUSTOM' ? chosen.custom?.height : undefined
  const paperSize = paperChoice === 'CUSTOM' ? (chosen.custom ? 'CUSTOM' : undefined) : paperChoice || undefined
  const scopeKey = `${sourceKey}:${refreshKey}:${pricingRevision}:${conduitMaterialId || ''}:${wireMaterialId || ''}:${paperSize || ''}:${customWidthMm || ''}:${customHeightMm || ''}:${wireMetersPerUnit ?? ''}:${wirePricePerMeter ?? ''}`
  const bom = loadedBOM?.scopeKey === scopeKey ? loadedBOM.value : null
  const planningOptions = loadedBOM?.sourceKey === sourceKey ? loadedBOM.value?.planning : null
  const pricing = useBOMPricing({projectId,floorId:floorPlanId ? planningOptions?.sources?.[0]?.floor_id:undefined,disabled:busy || unsaved || !designer,
    onVersionsChange:onPriceVersionsChange,onApplied:()=>{setPricingRevision(n=>n+1);onPricesApplied?.()}})
  useEffect(() => {
    const controller = new AbortController()
    fetchBOM(projectId, { signal: controller.signal, floorPlanId, processingJobId, conduitMaterialId, paperSize, wireMaterialId, customWidthMm, customHeightMm, wireMetersPerUnit, wirePricePerMeter }).then((value) => { if (!controller.signal.aborted) { setBOM({scopeKey,sourceKey,value}); setError('') } })
      .catch((failure) => { if (!controller.signal.aborted) { setBOM(null); setError(failure.message) } })
    return () => controller.abort()
  }, [projectId, floorPlanId, processingJobId, refreshKey, scopeKey, sourceKey, conduitMaterialId, paperSize, wireMaterialId, customWidthMm, customHeightMm, wireMetersPerUnit, wirePricePerMeter])
  useEffect(() => () => download.current?.abort(), [])
  async function exportSnapshot(draft = false) {
    if ((!draft && !estimate) || busy) return
    const controller = new AbortController(); download.current = controller
    setBusy(true)
    try {
      const blob = draft ? await downloadDraftBOM(projectId, { signal: controller.signal, floorPlanId, processingJobId, conduitMaterialId, paperSize, wireMaterialId, customWidthMm, customHeightMm, wireMetersPerUnit, wirePricePerMeter })
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
      <Button variant="ghost" disabled={pricing.locked} onClick={pricing.existing}>Saved price lists</Button></>}
    <Button variant="outline" disabled={!bom?.planning || busy} onClick={() => exportSnapshot(true)}>Download draft BOM</Button>
    {!floorPlanId && <Button variant="outline" disabled={!estimate || busy} onClick={() => exportSnapshot()}>{busy ? 'Downloading…' : 'Download saved BOM'}</Button>}</div></div>
    {unsaved && <p role="status">Unsaved changes: this BOM shows saved items. Save to refresh quantities.</p>}
    {designer && <BOMPricingControls model={pricing}/>}
    {planningOptions && <div className="studio-material-binding studio-bom-settings">
      <div className="studio-bom-setting"><h3>Conduit</h3>
      <label className="studio-field">Conduit product for this draft
        <select value={chosen.conduit || ''} onChange={event => setCalculation({...chosen,sourceKey,conduit:event.target.value})}>
          <option value="">Use saved mappings / exact matches</option>
          {orderNamed(planningOptions.conduit_materials || []).map(material => <option key={material.id} value={material.id}>{material.name} · {money(material.unit_price,material.currency)} per {material.unit}</option>)}
        </select>
      </label>
      <p>Conduit uses measured route length. Stick, roll or other purchase units require an explicit conversion; they are not assumed to equal one metre. Conductor quantities remain separate.</p>
      {!planningOptions.conduit_materials?.length && <p role="note">No priced conduit products yet. Admin must import the Excel catalog before conduit costs can be shown.</p>}
      </div>
      <div className="studio-bom-setting"><h3>Wire / cable</h3>
      <label className="studio-field">Wire / cable product for this draft
        <select value={chosen.wire || ''} onChange={event => setCalculation({...chosen,sourceKey,wire:event.target.value,
          wireMetersPerUnit:undefined,wirePricePerMeter:undefined})}>
          <option value="">Use saved circuit specifications</option>
          {orderNamed(planningOptions.wire_materials || []).map(material => <option key={material.id} value={material.id}>{material.name} · {money(material.unit_price,material.currency)} per {material.unit}</option>)}
        </select>
      </label>
      <form key={`${sourceKey}:${wireMaterialId || ''}`} onSubmit={event => {
        event.preventDefault()
        const data = new FormData(event.currentTarget)
        const length = data.get('wireLength'), price = data.get('wirePrice')
        setCalculation({...chosen,sourceKey,wireMetersPerUnit:length ? Number(length) : undefined,wirePricePerMeter:price === '' ? undefined : Number(price)})
      }}>
        {wireMaterialId && planningOptions.wire_materials?.find(m => m.id === wireMaterialId)?.unit !== 'meter' && <label className="studio-field">Metres per wire purchase unit
          <input name="wireLength" type="number" min="0.0001" max="100000" step="any" defaultValue={wireMetersPerUnit ?? planningOptions.wire_materials?.find(m => m.id === wireMaterialId)?.meters_per_unit ?? ''} placeholder="For example, the labelled roll length" />
        </label>}
        <label className="studio-field">Custom wire price per metre (PHP, optional)<input name="wirePrice" type="number" min="0" max="1000000000" step="0.01" defaultValue={wirePricePerMeter ?? ''} /></label>
        <Button type="submit" variant="outline">Apply wire pricing</Button>
      </form>
      <p role="note">Wire cost = cable route metres × price per metre. No extra allowance is added. Roll price is divided by metres per roll; a custom PHP price overrides it for this draft only. Conductor quantities still use saved circuit specifications.</p>
      </div>
      {floorPlanId && <div className="studio-bom-setting"><h3>Plan scale</h3>
      {floorPlanId && <label className="studio-field">Paper metadata (not calibration)
        <select value={paperChoice} onChange={event => setCalculation({...chosen,sourceKey,paper:event.target.value})}>
          <option value="">Use measured scale; otherwise leave unscaled</option>
          {['A4','A3','A2','A1','A0'].map(size => <option key={size} value={size}>{size}</option>)}
          <option value="CUSTOM">Custom sheet dimensions</option>
        </select>
      </label>}
      {paperChoice === 'CUSTOM' && <form onSubmit={event => {
        event.preventDefault()
        const data = new FormData(event.currentTarget)
        setCalculation({...chosen,sourceKey,paper:'CUSTOM',custom:{width:Number(data.get('width')),height:Number(data.get('height'))}})
      }}>
        <label className="studio-field">Sheet width (mm)<input key={`${sourceKey}:width`} name="width" type="number" min="0.01" max="10000" step="any" required defaultValue={customWidthMm ?? ''} /></label>
        <label className="studio-field">Sheet height (mm)<input key={`${sourceKey}:height`} name="height" type="number" min="0.01" max="10000" step="any" required defaultValue={customHeightMm ?? ''} /></label>
        <Button type="submit" variant="outline">Apply custom dimensions</Button>
      </form>}
      {paperChoice && <p role="note">Paper size alone cannot calibrate source pixels. Review a known real-world dimension in the project scale settings; uncalibrated path quantities remain pixels.</p>}
      </div>}
    </div>}
    {bom?.planning && <>
      {bom.planning.project_pricing && <p>Client prices · Version {bom.planning.project_pricing.version_number} · {bom.planning.project_pricing.filename}</p>}
      <p>Automatic from saved plan data. No per-item approvals. Save edits to update quantities.</p>
      {bom.planning.items.length || pricing.active ? <BOMTable planning={bom.planning} pricing={pricing} pricingLabels={pricingLabels}/> : <p>No saved devices or wiring yet.</p>}
      {bom.planning.unpriced_items > 0 && <p role="note">{bom.planning.unpriced_items} items are not costed. Subtotals are incomplete, not a project total.</p>}
      {bom.planning.missing_inputs?.map(note => <p role="note" key={note}>{note}</p>)}
      <details><summary>Calculation basis</summary><ul>{bom.planning.basis.map(note => <li key={note}>{note}</li>)}</ul>
        <p>{bom.planning.catalog_materials} active catalog materials. Prices use the confirmed client import when available, otherwise the Admin catalog. Missing prices are never treated as zero.</p></details>
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
