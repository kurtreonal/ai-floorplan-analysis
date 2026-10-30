import { useEffect, useState } from 'react'
import { applicationDefaults } from '../../api/applicationDefaults.js'
import { adminMaterialCatalog } from '../../api/materialPrices.js'
import { Button } from '../../components/ui/button.jsx'
import { workflowRequest } from '../../api/clientWorkflow.js'

export function AdminWiringPairs() {
  const [record, setRecord] = useState(null), [materials, setMaterials] = useState([]), [error, setError] = useState(''), [busy, setBusy] = useState(false), [message, setMessage] = useState('')
  const [editing,setEditing]=useState(null)
  useEffect(() => { const c = new AbortController(); Promise.all([applicationDefaults(null, c.signal), adminMaterialCatalog({ signal: c.signal })]).then(([r, m]) => { setRecord(r); setMaterials(m) }).catch(e => { if (!c.signal.aborted) setError(e.message) }); return () => c.abort() }, [])
  const pairs = record?.settings.wire_conduit_pairs || []
  const wires = materials.filter(m => m.is_active && ['meter','roll','length'].includes(m.unit) && (/wire|cable/i.test(m.name) || /(?:COPPER|FIBER)\s*(?:-\s*)?CABLES?/i.test(m.category)) && !/connector|gland|tie|tray|manager|clip|lug|patchcord|patch cord|panel/i.test(m.name))
  const conduits = materials.filter(m => m.is_active && ['meter','length','roll'].includes(m.unit) && /conduit/i.test(m.category) && /pipe|tube|tubing|conduit/i.test(m.name))
  async function save(event, removeId) {
    event?.preventDefault(); if (!record || busy) return
    const data = event ? new FormData(event.currentTarget) : null
    const next = removeId ? pairs.filter(p => p.wire_material_id !== removeId) : [...pairs.filter(p => p.wire_material_id !== Number(data.get('wire'))), {
      wire_material_id: Number(data.get('wire')), conduit_material_id: Number(data.get('conduit')), specification: data.get('specification'),
      wire_meters_per_unit: data.get('wireLength') ? Number(data.get('wireLength')) : null,
      conduit_meters_per_unit: data.get('conduitLength') ? Number(data.get('conduitLength')) : null,
      conductor_count: data.get('count') ? Number(data.get('count')) : null, assumed:data.get('assumed')==='on',
      under_floor_conduit_material_id:data.get('floorConduit') ? Number(data.get('floorConduit')) : null,
      under_floor_meters_per_unit:data.get('floorLength') ? Number(data.get('floorLength')) : null,
      conduit_options:data.getAll('conduitOption').map(Number),
    }]
    setBusy(true); setError(''); setMessage('')
    try { setRecord(await applicationDefaults({ ...record.settings, wire_conduit_pairs: next, expected_revision: record.revision })); setEditing(null);setMessage('Conduit choices saved.') }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  async function addProvisional(){
    if(!record||busy)return
    setBusy(true);setError('')
    try{const proposed=await workflowRequest('/admin/application-defaults/pairing-proposals');const existing=new Set(pairs.map(p=>p.wire_material_id));const added=proposed.filter(p=>!existing.has(p.wire_material_id));setRecord(await applicationDefaults({...record.settings,wire_conduit_pairs:[...pairs,...added],expected_revision:record.revision}));setMessage(`${added.length} provisional pairs added. Existing pairs were preserved.`)}catch(e){setError(e.message)}finally{setBusy(false)}
  }
  return <section className="workflow-panel"><h2>Wire &amp; conduit choices</h2><p>Choose a default conduit and the alternatives Designers may select for each wire product.</p>
    <p>Provisional pairs are editable budgeting assumptions. Unknown purchase lengths stay unset. Cable cores are not a conductor multiplier.</p>
    <Button variant="outline" disabled={busy||!record?.writable} onClick={addProvisional}>Add provisional defaults for unpaired wiring</Button>
    <details open={Boolean(editing)}><summary>{editing?'Edit selected pair':'Add a pair'}</summary><form key={editing?.wire_material_id||'new'} className="workflow-grid" onSubmit={save}><label className="studio-field">Wire / cable<select name="wire" required defaultValue={editing?.wire_material_id||''}><option value="">Choose wiring</option>{wires.map(m => <option key={m.id} value={m.id}>{m.name} · {m.unit}</option>)}</select></label>
      <label className="studio-field">Conduit<select name="conduit" required defaultValue={editing?.conduit_material_id||''}><option value="">Choose conduit</option>{conduits.map(m => <option key={m.id} value={m.id}>{m.name} · {m.unit}</option>)}</select></label>
      <label className="studio-field">Metres in one wire roll / length<input name="wireLength" defaultValue={editing?.wire_meters_per_unit??''} type="number" min="0.0001" max="100000" step="any"/></label>
      <label className="studio-field">Metres in one conduit roll / length<input name="conduitLength" defaultValue={editing?.conduit_meters_per_unit??''} type="number" min="0.0001" max="100000" step="any"/></label>
      <label className="studio-field">Individual conductors (if applicable)<input name="count" defaultValue={editing?.conductor_count??''} type="number" min="1" max="1000" step="1"/></label>
      <label className="studio-field">Circuit / installation basis<input name="specification" defaultValue={editing?.specification||''} required maxLength={500} placeholder="Product and installation basis for this pair"/></label>
      <label><input type="checkbox" name="assumed" defaultChecked={editing?.assumed??true}/>Provisional assumption</label>
      <details className="workflow-wide"><summary>Conduits Designer may choose</summary><p>Include each approved size and brand. The default and under-floor alternative are always included. Couplings included with pipe are already in its price.</p>
        <div className="conduit-choice-checklist">{conduits.map(m=><label key={m.id}><input type="checkbox" name="conduitOption" value={m.id} defaultChecked={editing?.conduit_options?.includes(m.id) || m.id===editing?.conduit_material_id || m.id===editing?.under_floor_conduit_material_id}/><span>{m.code?.split('-')[0]} · {m.name}</span></label>)}</div>
      </details>
      <details><summary>Under-floor alternative</summary><label className="studio-field">Under-floor conduit<select name="floorConduit" defaultValue={editing?.under_floor_conduit_material_id||''}><option value="">Use the same conduit</option>{conduits.map(m=><option key={m.id} value={m.id}>{m.name} · {m.unit}</option>)}</select></label><label className="studio-field">Metres per purchase unit<input name="floorLength" type="number" min="0.0001" max="100000" step="any" defaultValue={editing?.under_floor_meters_per_unit??''}/></label></details>
      <Button disabled={busy || !record?.writable} type="submit">Save compatible pair</Button>
    </form></details>{error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    <div className="studio-table-scroll"><table className="studio-project-table"><thead><tr><th>Wire / cable</th><th>Conduit</th><th>Basis</th><th>Action</th></tr></thead><tbody>{pairs.map(p => <tr key={p.wire_material_id}><td>{materials.find(m => m.id === p.wire_material_id)?.name}</td><td>{materials.find(m => m.id === p.conduit_material_id)?.name}{p.under_floor_conduit_material_id && p.under_floor_conduit_material_id!==p.conduit_material_id ? <small className="account-secondary">Under floor · {materials.find(m=>m.id===p.under_floor_conduit_material_id)?.name}</small>:null}</td><td><details><summary>{p.assumed?'Provisional':'Admin specified'}</summary>{p.specification}</details></td><td><Button variant="ghost" disabled={busy} onClick={()=>setEditing(p)}>Edit pair</Button><Button variant="ghost" disabled={busy} onClick={() => save(null, p.wire_material_id)}>Remove pair</Button></td></tr>)}</tbody></table></div>
  </section>
}
