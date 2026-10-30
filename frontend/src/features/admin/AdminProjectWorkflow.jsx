import { useEffect, useState } from 'react'
import { workflowRequest } from '../../api/clientWorkflow.js'
import { Button } from '../../components/ui/button.jsx'

export function AdminProjectWorkflow({ project, onChanged }) {
  const [accounts, setAccounts] = useState([]), [choices, setChoices] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false), [notice, setNotice] = useState('')
  const [clientId, setClientId] = useState(String(project.client_id || '')), [designerId, setDesignerId] = useState(String(project.intake_status==='pending_admin'?project.preferred_designer_id || '':project.owner_id || ''))
  const [estimateId, setEstimateId] = useState('')
  const [budgetEdit,setBudgetEdit]=useState(null)
  const budgetKey=`${project.id}:${project.allocated_budget}`
  const budget=budgetEdit?.key===budgetKey?budgetEdit.value:project.allocated_budget ?? ''
  const selectedEstimate = choices?.estimates.find(x => String(x.id) === estimateId)
  async function publishBOM(){
    setBusy(true);setError('');setNotice('')
    try{await workflowRequest(`/projects/${project.id}/approved-bom`,{method:'POST'});setNotice('Approved project BOM published to the client. Quantities and prices are captured.')}
    catch(e){setError(e.message)}finally{setBusy(false)}
  }
  useEffect(() => { const c = new AbortController(); Promise.all([workflowRequest('/admin/accounts', { signal: c.signal }), workflowRequest(`/projects/${project.id}/approval`, { signal: c.signal })])
    .then(([a, p]) => { setAccounts(a); setChoices(p) }).catch(e => { if (e.name !== 'AbortError') setError(e.message) }); return () => c.abort()
  }, [project.id])
  useEffect(() => { const c = new AbortController(); const refresh = () => workflowRequest('/admin/accounts', { signal: c.signal }).then(setAccounts).catch(e => { if (e.name !== 'AbortError') setError(e.message) }); window.addEventListener('ved:accounts-changed', refresh); return () => { c.abort(); window.removeEventListener('ved:accounts-changed', refresh) } }, [])
  async function submit(event, approval) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    const data = new FormData(event.currentTarget)
    const body = approval ? { layout_version_ids: selectedEstimate.layout_version_ids, estimate_id: selectedEstimate.id }
      : { client_id: Number(data.get('client')), designer_id: Number(data.get('designer')),allocated_budget:data.get('budget'),expected_details_revision:project.details_revision }
    try { const result = await workflowRequest(`/projects/${project.id}/${approval ? 'approval' : 'assignment'}`, { method: approval ? 'POST' : 'PUT', body });
      if (approval) setChoices(current => ({ ...current, approved_at: result.approved_at })); else onChanged?.()
      setNotice(approval ? 'Approved versions published to the client portal.' : 'Client and designer assignment saved.')
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  return <section className="workflow-panel"><h2>Assignment & client publication</h2>
    {project.intake_status==='pending_admin' && <p className="account-notice">Client submission awaiting review. {project.preferred_designer_name?`Preferred designer: ${project.preferred_designer_name}. `:''}Save an assignment to endorse it to the designer.</p>}
    <form className="workflow-grid" onSubmit={e => submit(e, false)}>
      <label className="studio-field">Client<select name="client" value={clientId} onChange={e => setClientId(e.target.value)} required><option value="">Choose client</option>{accounts.filter(x => x.role === 'CLIENT' && !x.disabled && x.username).map(x => <option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
      <label className="studio-field">Assigned designer<select name="designer" value={designerId} onChange={e => setDesignerId(e.target.value)} required><option value="">Choose designer</option>{accounts.filter(x => x.role === 'DESIGNER' && !x.disabled && x.username).map(x => <option key={x.id} value={x.id}>{x.label} · #{x.id}</option>)}</select><small>{accounts.filter(x => x.role === 'DESIGNER' && !x.disabled && x.username).length} available designers · Admin settings → Users</small></label>
      <label className="studio-field">Allocated budget (PHP)<input name="budget" type="number" min="0" step="0.01" max="999999999999.99" required value={budget} onChange={event=>setBudgetEdit({key:budgetKey,value:event.target.value})} disabled={busy}/></label><Button type="submit" variant="outline" disabled={busy}>Save assignment</Button>
    </form>
    <details><summary>Client publication</summary><p>Approving a Designer proposal also publishes its project BOM. Publish again here to adopt updated prices for approved plans.</p><Button variant="outline" disabled={busy} onClick={publishBOM}>Publish approved project BOM</Button><p>Or publish a saved estimate and its captured layouts:</p>
      {choices && <form className="workflow-grid" onSubmit={e => submit(e, true)}>
        <label className="studio-field">Estimate snapshot<select name="estimate" value={estimateId} onChange={e => setEstimateId(e.target.value)} required><option value="">Choose saved estimate</option>{choices.estimates.map(x => <option key={x.id} value={x.id} disabled={!x.layout_version_ids?.length}>Version {x.version} · {x.currency} {Number(x.total).toLocaleString()}{!x.layout_version_ids?.length ? ' · No captured layouts' : ''}</option>)}</select></label>
        {selectedEstimate && <div><strong>Included saved layouts</strong><p>{choices.layouts.filter(x => selectedEstimate.layout_version_ids.includes(x.id)).map(x => `Floor ${x.floor_id} · Version ${x.version}`).join(', ')}</p><small>Bound to this estimate automatically. Later edits remain private.</small></div>}
        <label className="account-check"><input type="checkbox" required/>I reviewed this planning estimate and its saved layouts for client publication.</label>
        <Button type="submit" disabled={busy || !selectedEstimate?.layout_version_ids?.length}>Approve & publish to client</Button>
        {(!choices.layouts.length || !choices.estimates.length) && <small>The Designer must save the layout, then generate an estimate in Cost estimation. Downloading the draft BOM does not create a saved estimate.</small>}
        {choices.approved_at && <small>Last publication: {new Date(choices.approved_at).toLocaleString()}</small>}
      </form>}
    </details>{error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
  </section>
}
