import {Button} from '../../components/ui/button.jsx'

const papers={A0:[841,1189],A1:[594,841],A2:[420,594],A3:[297,420],A4:[210,297],A5:[148,210]}
const basisLabels={source_sheet:'Source sheet',known_reference:'Known reference',estimated:'Estimated',needs_reference:'Needs reference'}

export function SheetControls({model,context={},canSave,onImproveAccuracy,needsArea=false,draft,advancedOpen=false}) {
  const values=model?.values,metric=model?.record?.effective_measurement || context
  if(!values)return <p role="status">{model?.error || 'Loading plan measurements…'}{model?.error && <Button onClick={model.reload}>Retry</Button>}</p>
  const automatic=values.height_mode==='automatic' && values.service_height_above_floor_meters==null && values.fixture_center_height_meters==null && values.fixture_connection_height_meters==null
  const customItems=(draft?.symbols || []).filter(s=>s.disposition!=='rejected' && s.mounting_height_meters!=null).length
    +(draft?.wirings || []).filter(w=>w.disposition!=='rejected' && (w.elevation_meters!=null || w.height_above_floor_meters!=null)).length
  const ceiling=metric.ceiling_height_meters
  const warnings=(draft?.symbols || []).some(s=>s.disposition!=='rejected' && s.mounting_height_meters!=null && s.mounting_height_meters+(s.terminal_offset_meters ?? 0)>ceiling && ceiling>0)
    || (draft?.wirings || []).some(w=>w.disposition!=='rejected' && w.installation_method==='concealed_in_ceiling' && ceiling>0 &&
      (w.height_above_floor_meters!=null ? Math.abs(w.height_above_floor_meters-ceiling)>.01 : w.elevation_meters!=null && context.floor_elevation_meters!=null && Math.abs(w.elevation_meters-context.floor_elevation_meters-ceiling)>.01))
    || ceiling>0 && [values.fixture_center_height_meters,values.fixture_connection_height_meters].some(v=>v!=null && v>ceiling)
    || ceiling>0 && values.service_height_above_floor_meters!=null && Math.abs(values.service_height_above_floor_meters-ceiling)>.01
  const scale=metric.measurement_state==='known_reference' ? 'Known reference'
    : metric.measurement_state==='estimated' ? `Estimated · ${metric.assumed_paper_size || values.source_paper_size} at 1:${metric.scale_denominator || values.scale_denominator}`
    : metric.measurement_state==='source_sheet' ? `Source sheet · 1:${metric.scale_denominator}`
    : metric.scale_reason==='not_to_scale_view' ? 'Not to scale (NTS)' : needsArea ? 'Select one plan area':'Needs reference'
  return <div className="studio-sheet-fields">
    <dl className="measurement-setup-summary"><div><dt>Setup</dt><dd>{automatic ? 'Automatic':'Custom'}</dd></div>
      <div><dt>Ceiling height</dt><dd>{ceiling>0 ? `${ceiling} m`:'Not set'}</dd></div><div><dt>Scale</dt><dd>{scale}</dd></div></dl>
    {(metric.estimated || metric.height_basis==='assumed') && <small className="measurement-basis">Estimated · planning assumptions</small>}
    <Button data-automatic-setup disabled={!canSave || model.status==='saving'} onClick={model.onAutomatic}>{model.status==='saving' ? 'Resetting…':'Reset setup'}</Button>
    <Button variant="outline" disabled={!canSave || needsArea || model.status==='saving'} onClick={onImproveAccuracy}>Improve accuracy</Button>
    <small>Improve accuracy with one known distance or a scale bar.</small>
    <small>Scanned plans start with Admin measurement defaults. Reset setup reapplies them{customItems ? ` and preserves ${customItems} custom items` : ''}.</small>
    {warnings && <small role="alert">Custom heights differ from the ceiling setup. Check them in Advanced settings or the item inspector.</small>}
    {model.error && <small role="alert">{model.error} <button type="button" onClick={model.reload}>Reload settings</button></small>}
    {model.status==='saved' && <small role="status">Plan setup saved. Draft geometry is unchanged.</small>}
    <details className="measurement-advanced" open={advancedOpen || undefined}><summary>Advanced settings{model.dirty ? ' · not applied':''}</summary>
      <AdvancedMeasurementControls model={model} context={context} canSave={canSave}/>
    </details>
  </div>
}

function AdvancedMeasurementControls({model,context={},canSave}) {
  const v=model?.values
  if(!v)return <p role="status">{model?.error || 'Loading plan measurements…'}{model?.error && <Button onClick={model.reload}>Retry</Button>}</p>
  const method=v.measurement_method || 'auto',paper=['full_sheet','estimated'].includes(method)
  const custom=v.source_paper_size==='CUSTOM',busy=model.status==='saving'
  const metric=model.record?.effective_measurement || context
  const native=metric.source_width_mm>0
  const valid=Number(v.scale_denominator)>=1 && Number(v.scale_denominator)<=100000
    && (!paper || !custom || [v.source_width_mm,v.source_height_mm].every(x=>Number(x)>0 && Number(x)<=10000))
    && (method!=='full_sheet' || v.full_sheet_confirmed) && (method!=='reference' || v.reference)
    && ['outlet_center_height_meters','switch_center_height_meters'].every(k=>v[k]!=null && Number(v[k])>=0 && Number(v[k])<=100)
    && ['service_height_above_floor_meters','fixture_center_height_meters','fixture_connection_height_meters'].every(k=>v[k]==null || Number(v[k])>=0 && Number(v[k])<=100)
    && (v.floor_to_ceiling_height_meters==null || Number(v.floor_to_ceiling_height_meters)>0 && Number(v.floor_to_ceiling_height_meters)<=100)
    && (v.height_mode!=='automatic' || Number(v.floor_to_ceiling_height_meters)>0)
  return <fieldset className="studio-sheet-fields" disabled={busy || !canSave}>
    <legend className="sr-only">Plan measurements</legend>
    <strong className="measurement-basis">{basisLabels[model.dirty && method==='estimated' ? 'estimated':metric.measurement_state] || 'Needs reference'}{model.dirty ? ' · not applied':''}</strong>
    <label>How to find the real size<select aria-label="Measurement method" value={method} onChange={e=>model.update({measurement_method:e.target.value})}>
      <option value="auto">{metric.scale_basis==='paper_ruler_draft' ? 'Keep existing paper estimate':metric.measurement_state==='known_reference' ? 'Keep known reference':native ? 'Original PDF sheet (automatic)':'Choose a measurement basis'}</option>
      {native && <option value="source_sheet">Original PDF sheet</option>}
      <option value="full_sheet">Scan of the complete paper sheet</option>
      {v.reference && <option value="reference">Known distance measured with ruler</option>}
      <option value="estimated">Estimate from paper size</option>
      <option value="not_to_scale">Diagram without a scale (NTS)</option>
    </select></label>
    {native && !paper && method!=='reference' && <small>Original PDF: {metric.source_width_mm.toFixed(1)} × {metric.source_height_mm.toFixed(1)} mm.</small>}
    {!['reference','not_to_scale'].includes(method) && <>
      <label className="studio-scale-denominator">Drawing scale<span className="studio-scale-number"><span aria-hidden="true">1 :</span><input aria-label="Drawing scale denominator" type="number" min="1" max="100000" step="any" value={v.scale_denominator}
        onChange={e=>model.update({scale_denominator:e.target.value==='' ? '':Number(e.target.value),drawing_scale_confirmed:true})}/></span></label>
      <small>{metric.ratio_assumed && !v.drawing_scale_confirmed ? '1:N is assumed. Check the label on this plan.':'10 mm on the original sheet at 1:100 represents 1 metre.'}</small>
      {(metric.ratio_assumed || paper) && <label className="measurement-check"><input type="checkbox" checked={Boolean(v.drawing_scale_confirmed)} onChange={e=>model.update({drawing_scale_confirmed:e.target.checked})}/>This is the drawing’s labelled scale</label>}
    </>}
    {paper && <>
      <label>Original paper size<select aria-label="Original paper size" value={v.source_paper_size || 'A1'} onChange={e=>model.update({source_paper_size:e.target.value})}>
        {['A1','A2','A3','A4','A5'].map(p=><option key={p}>{p}</option>)}{v.source_paper_size==='A0' && <option>A0</option>}<option value="CUSTOM">Custom</option>
      </select></label>
      <label>Original orientation<select aria-label="Original orientation" value={v.source_orientation || ''} onChange={e=>model.update({source_orientation:e.target.value || null})}><option value="">Follow image</option><option value="landscape">Landscape</option><option value="portrait">Portrait</option></select></label>
      {custom && <div className="bom-paper-dimensions">{[['source_width_mm','Width'],['source_height_mm','Height']].map(([key,label])=><label key={key}>{label} (mm)<input type="number" min="0.001" max="10000" step="any" value={v[key] ?? ''} onChange={e=>model.update({[key]:e.target.value==='' ? null:Number(e.target.value)})}/></label>)}</div>}
      {method==='full_sheet' ? <label className="measurement-check"><input type="checkbox" checked={Boolean(v.full_sheet_confirmed)} onChange={e=>model.update({full_sheet_confirmed:e.target.checked})}/>This is a complete, flat scan with its original paper edges—not a perspective photo</label>
        : <><label>Image size on paper <output>{v.image_size_percent ?? 100}%</output><input aria-label="Image size on paper" type="range" min="1" max="100" value={v.image_size_percent ?? 100} onChange={e=>model.update({image_size_percent:Number(e.target.value)})}/></label><small>Estimated from assumed paper placement.</small></>}
      <PaperPreview values={v} binding={model.record?.measurement_context}/>
    </>}
    {method==='auto' && metric.measurement_state==='estimated' && <small>This paper-placement assumption is an estimate, not a known-distance calibration.</small>}
    {method==='auto' && metric.measurement_state==='needs_reference' && !metric.multiple_scale_views && <small>Use a complete original sheet, one labelled dimension/scale bar, or explicitly choose a rough estimate.</small>}
    {metric.scale_reason==='sheet_edges_or_reference_required' && <small role="alert">The image proportions do not match that sheet. Use its paper edges or a known reference instead.</small>}
    {method==='not_to_scale' && <small>NTS diagrams have no measured wiring quantity. Devices can still be counted and priced.</small>}
    <div className="measurement-heights">
      <small>Metres above finished floor. In automatic setup, blank ceiling-route and light-connection overrides follow the ceiling. Individual saved heights take priority.</small>
      {[
        ['floor_to_ceiling_height_meters','Ceiling height'],['service_height_above_floor_meters','Ceiling wire height · blank follows ceiling'],['fixture_connection_height_meters','Light wire connection · blank follows ceiling'],
        ...(v.fixture_center_height_meters!=null ? [['fixture_center_height_meters','Legacy lighting centre height']]:[]),
        ['outlet_center_height_meters','Outlet centre height'],['switch_center_height_meters','Switch centre height'],
      ].map(([key,label])=><label key={key}>{label} (m)<input aria-label={label} type="number" min="0" max="100" step="0.01" value={v[key] ?? ''} onChange={e=>model.update({[key]:e.target.value==='' ? null:Number(e.target.value)})}/></label>)}
    </div>
    <Button size="sm" disabled={!valid || !model.dirty || busy} onClick={()=>model.onSave()}>{busy ? 'Applying…':'Apply measurements'}</Button>
    {model.error && <small role="alert">{model.error} <button type="button" onClick={model.reload}>Reload settings</button></small>}
    {model.status==='saved' && <small role="status">Measurements saved.</small>}
  </fieldset>
}

function PaperPreview({values:v,binding}) {
  const dimensions=v.source_paper_size==='CUSTOM' ? [Number(v.source_width_mm),Number(v.source_height_mm)]:papers[v.source_paper_size || 'A1']
  if(!dimensions?.every(x=>x>0))return null
  const iw=binding?.width_pixels || 4,ih=binding?.height_pixels || 3
  const landscape=(v.source_orientation || (iw>=ih ? 'landscape':'portrait'))==='landscape'
  const [short,long]=[...dimensions].sort((a,b)=>a-b),[pw,ph]=landscape ? [long,short]:[short,long]
  const fit=Math.min(pw/iw,ph/ih)*(v.measurement_method==='estimated' ? (v.image_size_percent ?? 100)/100:1)
  const w=iw*fit,h=ih*fit
  return <svg className="measurement-paper-preview" viewBox={'0 0 '+pw+' '+ph} role="img" aria-label="Assumed image placement on original paper">
    <rect x="1" y="1" width={pw-2} height={ph-2} fill="var(--white)" stroke="var(--paper-line)" strokeWidth="3"/>
    <rect x={(pw-w)/2} y={(ph-h)/2} width={w} height={h} fill="rgba(255,122,69,.12)" stroke="var(--orange)" strokeWidth="3"/>
    <text x={pw/2} y={ph/2} textAnchor="middle" dominantBaseline="middle" fontSize={Math.min(pw,ph)*.07} fill="var(--ink)">Uploaded image</text>
  </svg>
}

export function DisplayPaperControls({model,canSave}) {
  const v=model?.values
  if(!v)return <p>Loading display settings…</p>
  const dirty=['display_paper_size','display_orientation','display_width_mm','display_height_mm'].some(k=>v[k]!==model.record?.settings[k])
  return <fieldset className="studio-sheet-fields" disabled={!canSave || model.status==='saving'}><legend>Display / print paper</legend>
    <small>Changes the page frame only—not measured lengths or prices.</small>
    <label>Display paper<select aria-label="Display paper" value={v.display_paper_size} onChange={e=>model.update({display_paper_size:e.target.value})}><option value="ORIGINAL">Original page</option>{['A1','A2','A3','A4','A5'].map(p=><option key={p}>{p}</option>)}{v.display_paper_size==='A0' && <option>A0</option>}<option value="CUSTOM">Custom</option></select></label>
    <label>Orientation<select aria-label="Orientation" value={v.display_orientation || ''} onChange={e=>model.update({display_orientation:e.target.value || null})}><option value="">Original orientation</option><option value="landscape">Landscape</option><option value="portrait">Portrait</option></select></label>
    {v.display_paper_size==='CUSTOM' && <div className="bom-paper-dimensions">{[['display_width_mm','Width'],['display_height_mm','Height']].map(([key,label])=><label key={key}>{label} (mm)<input type="number" min="0.001" max="10000" step="any" value={v[key] ?? ''} onChange={e=>model.update({[key]:e.target.value==='' ? null:Number(e.target.value)})}/></label>)}</div>}
    <Button disabled={!dirty || v.display_paper_size==='CUSTOM' && ![v.display_width_mm,v.display_height_mm].every(x=>Number(x)>0)} onClick={()=>model.onSaveDisplay()}>Apply display layout</Button>
    {model.error && <small role="alert">{model.error}</small>}
  </fieldset>
}
