import { Button } from '../../components/ui/button.jsx'
import { useState } from 'react'
import {ConduitProductInput} from './ConduitProductInput.jsx'
import {DeviceProductChoice} from './DeviceProductChoice.jsx'

const money = material => material.unit_price==null ? 'Price needed':new Intl.NumberFormat(undefined, { style: 'currency', currency: material.currency || 'PHP' }).format(Number(material.unit_price))

export function ManualBOMSettings({ options, values, onChange, disabled,editorId,focusField }) {
  const [wire, setWire] = useState(String(values.wire || options.selected_wire_material_id || options.items?.find(r=>r.material_kind==='wire' && r.material_id)?.material_id || ''))
  const [conduitId,setConduitId]=useState(values.conduit || '')
  const [wirePrice, setWirePrice] = useState(values.purchasePricing?.wire?.price ?? '')
  const [wireLength, setWireLength] = useState(values.purchasePricing?.wire?.meters_per_unit ?? values.wireMetersPerUnit ?? '')
  const [conduitPrice, setConduitPrice] = useState(values.purchasePricing?.conduit?.price ?? '')
  const [conduitLength, setConduitLength] = useState(values.purchasePricing?.conduit?.meters_per_unit ?? '')
  const [conductorCount,setConductorCount]=useState(values.conductorCount ?? values.automaticDefaults?.conductor_count ?? options.items?.find(row=>row.material_kind==='wire' && row.conductor_count)?.conductor_count ?? options.default_conductor_count ?? '')
  const [countEdited,setCountEdited]=useState(false)
  const selectedWire = options.wire_materials?.find(m => String(m.id) === wire)
  const currentWire = options.items?.find(row => row.material_kind === 'wire' && row.material_id) || options.items?.find(row => row.material_kind === 'wire')
  const priceWire = selectedWire || options.wire_materials?.find(m => m.id === currentWire?.material_id)
  const effectiveWireId = selectedWire?.id || currentWire?.material_id
  const pair = options.wire_conduit_pairs?.find(p => p.wire_material_id === effectiveWireId)
  const placementCounts=(options.items || []).filter(r=>r.material_kind==='wire').reduce((all,row)=>({...all,[row.installation_method || 'unknown']:(all[row.installation_method || 'unknown'] || 0)+(row.path_ids?.length || 1)}),{})
  const primaryPlacement=Object.keys(placementCounts).sort((a,b)=>placementCounts[b]-placementCounts[a])[0]
  const underFloor = primaryPlacement === 'concealed_under_floor' && pair?.under_floor_conduit_material_id
  const allowed=new Set([pair?.conduit_material_id,pair?.under_floor_conduit_material_id,...(pair?.conduit_options || [])])
  const conduits=(options.conduit_materials || []).filter(m=>allowed.has(m.id))
  const displayedConduitId=conduitId || String((underFloor ? pair?.under_floor_conduit_material_id:pair?.conduit_material_id) || '')
  const conduit = conduits.find(m => String(m.id)===displayedConduitId)
  const wireUnit = priceWire?.unit || currentWire?.unit || 'meter', conduitUnit = conduit?.unit || 'meter'
  const wireFactor = wireUnit === 'meter' ? 1 : Number(wireLength || priceWire?.meters_per_unit || pair?.wire_meters_per_unit || currentWire?.purchase_meters_per_unit)
  const pairConduitLength = underFloor ? pair.under_floor_meters_per_unit : pair?.conduit_meters_per_unit
  const conduitFactor = conduitUnit === 'meter' ? 1 : Number(conduitLength || conduit?.meters_per_unit || pairConduitLength)
  const wireQuote = selectedWire || currentWire
  // Current BOM rows may carry a normalized client rate per metre, while the
  // catalog product is sold by roll. Keep the input amount in its labelled unit.
  const normalizedWireRate = !selectedWire && currentWire?.unit === 'meter' && wireUnit !== 'meter'
  const currentWirePrice = wireQuote?.currency === 'PHP' && wireQuote.unit_price != null
    ? normalizedWireRate ? wireFactor > 0 ? Number(wireQuote.unit_price) * wireFactor : ''
      : wireQuote.unit === wireUnit ? wireQuote.unit_price : ''
    : ''
  const legacyWirePrice = values.wirePricePerMeter != null && wireFactor > 0 ? Number(values.wirePricePerMeter) * wireFactor : ''
  const wireDisplayPrice = wirePrice === '' ? !selectedWire && legacyWirePrice !== '' ? legacyWirePrice : currentWirePrice : wirePrice
  const conduitDisplayPrice = conduitPrice === '' ? conduit?.currency === 'PHP' ? conduit.unit_price ?? '' : '' : conduitPrice
  function chooseWire(id) { setWire(id);setConduitId(''); setWirePrice(''); setWireLength(''); setConduitPrice(''); setConduitLength('') }
  return <details id={editorId} className="bom-manual-settings" open={focusField ? true:undefined}><summary>Material prices</summary>
    <form onSubmit={event => {
      event.preventDefault()
      const data = new FormData(event.currentTarget), purchases = {}
      const connectionChoice=event.currentTarget.elements.namedItem('assume-connections')
      if (priceWire && (wirePrice !== '' || wireLength !== '')) purchases.wire = { material_id: priceWire.id, ...(wirePrice!=='' ? {price:Number(wireDisplayPrice)}:{}), ...(wireFactor>0?{meters_per_unit:wireFactor}:{}) }
      if (conduit && (conduitPrice !== '' || conduitLength !== '') && conduitFactor > 0) purchases.conduit = { material_id: conduit.id,...(conduitPrice!=='' ? {price:Number(conduitDisplayPrice)}:{}), meters_per_unit: conduitFactor }
      onChange({ wire:wire || ((purchases.wire || purchases.conduit || conduitId) && priceWire ? String(priceWire.id):''),conduit:conduitId || (purchases.conduit ? String(conduit.id):''), purchasePricing: purchases,
        ...(conductorCount!=='' && (countEdited || values.conductorCount!=null)?{conductorCount:Number(conductorCount)}:{}),
        ...(connectionChoice?.dataset.changed ? {assumeConnections:data.get('assume-connections')==='on'}:{}),
        wireMetersPerUnit: selectedWire && wireFactor > 0 ? wireFactor : undefined,
        wirePricePerMeter: !priceWire && wirePrice !== '' && wireFactor > 0 ? Number(wirePrice)/wireFactor : undefined,
        deviceMaterials: Object.fromEntries((options.device_groups || []).map(group => [String(group.class_id), data.get('device-' + group.class_id)])
          .filter(([, id]) => id).map(([id, material]) => [id, Number(material)])) })
    }}><fieldset disabled={disabled}>
      <p>{options.scope==='plan' ? 'For this plan.':'Project defaults. Individual plan choices take priority.'}</p>
      <label className="measurement-check"><input type="checkbox" name="assume-connections" defaultChecked={Boolean(values.assumeConnections)} onChange={e=>{e.currentTarget.dataset.changed='true'}}/>Use estimated connections for suggested routes</label>
      <div className="studio-material-binding studio-bom-settings">
        <div className="studio-bom-setting"><h3>1 · Wire / cable</h3>
          <label className="studio-field">Wire / cable product<select data-material-field="wire-product" autoFocus={focusField==='wire-product'} name="wire" value={wire} onChange={e => chooseWire(e.target.value)}>
            <option value="">Choose the wire / cable product</option>
            {(options.wire_materials || []).map(m => <option key={m.id} value={m.id}>{m.name} · {money(m)} / {m.unit}</option>)}
          </select></label>
          {(selectedWire || currentWire) && <small className="bom-selected-product">{selectedWire?.name || currentWire.client_product_name || currentWire.material_name || 'Current uploaded wire price'}</small>}
          <label className="studio-field">Wire / cable price / {wireUnit === 'meter' ? 'metre' : wireUnit} (PHP)<input type="number" min="0" max="1000000000" step="any" placeholder="Use current price" value={wireDisplayPrice} onChange={e => setWirePrice(e.target.value)}/></label>
          {(/\b(?:THHN|THW|single[ -]?core|single conductor)\b/i.test(priceWire?.name || '') || focusField==='conductor-count') && <label className="studio-field">Default individual wires per path<input data-material-field="conductor-count" autoFocus={focusField==='conductor-count'} type="number" min="1" max="1000" step="1" required value={conductorCount} onChange={e=>{setConductorCount(e.target.value);setCountEdited(true)}}/><small>Filled from the plan setup. Three separate wires on a 10 m path need 30 m of wire. Individual path settings take priority.</small></label>}
          {normalizedWireRate && wireFactor > 0 && wirePrice === '' && <small>Current metre rate × {wireFactor} m / {wireUnit}. Applying an edited price uses whole purchase units.</small>}
          {wireQuote?.currency && wireQuote.currency !== 'PHP' && <small>Current price is in {wireQuote.currency}. Enter a PHP override only if needed.</small>}
          {wireUnit !== 'meter' && <label className="studio-field">Metres per {wireUnit}<input autoFocus={focusField==='wire-length'} data-material-field="wire-length" aria-describedby="wire-length-help" type="number" min="0.0001" max="100000" step="any" placeholder="Length printed on the roll / pack" value={wireLength || priceWire?.meters_per_unit || pair?.wire_meters_per_unit || currentWire?.purchase_meters_per_unit || ''} onChange={e => setWireLength(e.target.value)}/></label>}
          {wireUnit!=='meter' && !(wireFactor>0) && <small id="wire-length-help" className="bom-required-input">Enter the metres in one {wireUnit} to calculate its cost. This length is missing from the supplied price sheet. You can save the product now and fill this in later.</small>}
        </div>
        <div className="studio-bom-setting"><h3>2 · Compatible conduit</h3>
          <label className="studio-field">Conduit product<ConduitProductInput products={conduits} value={displayedConduitId} disabled={!pair}
            onChange={id=>{setConduitId(id);setConduitPrice('');setConduitLength('')}}/></label>
          {conduit && <small className="bom-selected-product">{conduit.name.replace(/^EMT pipe/i,'EMT tubing')}</small>}
          {conduit && /with.*coupling/i.test(conduit.name) && <small>One coupling is included per length.</small>}
          {conduit && /\b(?:EMT|PVC)\b/i.test(conduit.name) && <small>Fittings are priced separately.</small>}
          {!pair && <small>Choose a wire product to see conduit sizes.</small>}
          {pair && <small>{pair.assumed ? 'Estimated pair · Editable by Admin' : 'Admin-specified pair'}</small>}
          {conduit && <><label className="studio-field">Conduit price / {conduitUnit === 'meter' ? 'metre' : conduitUnit} (PHP)<input type="number" min="0" max="1000000000" step="any" value={conduitDisplayPrice} onChange={e => setConduitPrice(e.target.value)}/></label>
            {conduitUnit !== 'meter' && <label className="studio-field">Metres per {conduitUnit}<input data-material-field="conduit-length" autoFocus={focusField==='conduit-length'} type="number" min="0.0001" max="100000" step="any" required value={conduitLength || conduit?.meters_per_unit || pairConduitLength || ''} onChange={e => setConduitLength(e.target.value)}/></label>}</>}
          <small>{conduitId ? `Selected for ${options.scope==='plan'?'this plan':'project defaults'}.`:`Current ${underFloor?'under-floor':'ceiling / general'} default shown. Type a size or brand to change it.`}</small>
        </div>
        <div className="studio-bom-setting bom-device-setting"><h3>Devices</h3>
          <div className="bom-device-options">{(options.device_groups || []).map(group => <DeviceProductChoice key={group.class_id} group={group} value={values.deviceMaterials?.[group.class_id]} focus={focusField===`device-${group.class_id}`}/>)}</div>{!options.device_groups?.length && <small>No classified devices on this plan.</small>}
        </div>
      </div><div className="bom-material-actions"><Button variant="outline" type="submit">Apply material prices</Button></div>
    </fieldset></form>
  </details>
}
