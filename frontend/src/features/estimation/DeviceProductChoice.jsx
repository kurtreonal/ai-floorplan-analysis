import {useState} from 'react'
import {legendDescription} from '../../api/legendChoices.js'

const brandKey=product=>product.brand || 'Brand not specified'
export function DeviceProductChoice({group,value,focus=false}) {
  const [chosen,setChosen]=useState(()=>({id:String(value || group.selected_material_id || ''),explicit:Boolean(value)}))
  const selected=group.materials.find(m=>String(m.id)===chosen.id)
  const [brand,setBrand]=useState(()=>selected?brandKey(selected):'')
  const brands=[...new Set(group.materials.map(brandKey))].sort((a,b)=>a.localeCompare(b))
  const products=group.materials.filter(m=>!brand || brandKey(m)===brand)
  const money=m=>m.unit_price==null?'Price needed':new Intl.NumberFormat(undefined,{style:'currency',currency:m.currency || 'PHP'}).format(Number(m.unit_price))
  return <div className="bom-device-choice"><h4>{legendDescription(group.name)} <span className="bom-device-count">× {group.quantity}</span></h4>
    <label className="studio-field">Brand<select aria-label={`Brand for ${legendDescription(group.name)}`} data-material-field={`device-${group.class_id}`} autoFocus={focus} value={brand} disabled={!brands.length} onChange={event=>{const next=event.target.value;setBrand(next);setChosen({id:String(group.materials.find(m=>brandKey(m)===next)?.id || ''),explicit:true})}}><option value="">All available brands</option>{brands.map(name=><option key={name} value={name}>{name}</option>)}</select></label>
    <label className="studio-field">Product<select name={chosen.explicit?`device-${group.class_id}`:undefined} aria-label={`Approved product for ${legendDescription(group.name)}`} value={chosen.id} onChange={event=>setChosen({id:event.target.value,explicit:true})}>
      <option value="">{group.materials.length?'Use client price / VED default':'No compatible catalogue product'}</option>{products.map(m=><option key={m.id} value={m.id}>{m.name} · {money(m)} / {m.unit}</option>)}
    </select></label>{selected?.code && <small>Item {selected.code}</small>}
    {brands.length===1 && <small>Only {brands[0]} is currently listed for this device. Admin can add other compatible products.</small>}
    <small>Apply to update this device type in the BOM. Saved estimates stay unchanged.</small>
  </div>
}
