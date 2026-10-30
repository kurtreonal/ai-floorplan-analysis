import {API_BASE_URL} from '../../api/auth.js'

export function LegendArtworkPicker({value,onChange,references,referenceError,editing,disabled}){
  const choice=references.find(row=>row.id===value.referenceId)
  return <section className="legend-artwork-picker" aria-label="Legend symbol image">
    <label>Symbol image<select disabled={disabled} value={value.kind} onChange={event=>onChange({kind:event.target.value,referenceId:'',file:null})}><option value="auto">{editing?'Keep current image':'Automatic from source'}</option><option value="pec" disabled={!references.length}>Choose from supplied PEC</option><option value="upload">Upload an image</option></select></label>
    {value.kind==='auto' && <small>Uses the drawing symbol or an existing PEC match. Device types and prices stay unchanged.</small>}
    {value.kind==='pec' && <><label>PEC device symbol<select required disabled={disabled} value={value.referenceId} onChange={event=>onChange({...value,referenceId:event.target.value})}><option value="">Choose a symbol</option>{references.map(row=><option key={row.id} value={row.id}>{row.label} · {row.reference}</option>)}</select></label>{choice && <div className="legend-reference-preview"><img alt={choice.label} crossOrigin="use-credentials" src={`${API_BASE_URL}/api/symbol-legends/reference-images/${choice.id}.png`}/><div><strong>{choice.label}</strong><small>Supplied PEC · {choice.reference}</small></div></div>}</>}
    {value.kind==='upload' && <label>Image file<input required disabled={disabled} type="file" accept="image/png,image/jpeg,image/webp" onChange={event=>onChange({...value,file:event.target.files?.[0] || null})}/><small>PNG, JPEG or WebP · up to 2 MB.</small></label>}
    {referenceError && <small>{referenceError}</small>}
    <small>Symbol image only. This does not retrain the detector.</small>
  </section>
}
