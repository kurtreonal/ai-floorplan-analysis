import {useEffect,useRef,useState} from 'react'
import {AlertTriangle,Archive} from 'lucide-react'
import {workflowRequest} from '../../api/clientWorkflow.js'
import {Button} from '../../components/ui/button.jsx'
import {AccountDialog} from '../settings/AccountDialog.jsx'
import './workspaceReset.css'

const active=phase=>['pending','executing','cleaning','recovery_required'].includes(phase)
export function AdminWorkspaceReset(){
  const [state,setState]=useState(null),[dialog,setDialog]=useState(false),[confirmation,setConfirmation]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[requestId,setRequestId]=useState('')
  const [designerId,setDesignerId]=useState('')
  const [clock,setClock]=useState(()=>({server:Date.now(),received:Date.now()})),[tick,setTick]=useState(()=>Date.now())
  const previousPhase=useRef(null)
  function receive(value){setState(current=>({...current,...value}));setClock({server:Date.parse(value.server_time),received:Date.now()});if(previousPhase.current&&previousPhase.current!=='completed'&&value.phase==='completed')window.dispatchEvent(new Event('ved:accounts-changed'));previousPhase.current=value.phase}
  useEffect(()=>{
    const controller=new AbortController()
    workflowRequest('/admin/workspace-reset',{signal:controller.signal}).then(value=>{if(!controller.signal.aborted)receive(value)}).catch(e=>{if(!controller.signal.aborted)setError(e.message)})
    const timer=window.setInterval(()=>{if(document.hidden)return;workflowRequest('/admin/workspace-reset/status',{signal:controller.signal}).then(value=>{if(!controller.signal.aborted)receive(value)}).catch(e=>{if(!controller.signal.aborted)setError(e.message)})},5000)
    const seconds=window.setInterval(()=>setTick(Date.now()),1000)
    return()=>{controller.abort();window.clearInterval(timer);window.clearInterval(seconds)}
  },[])
  async function open(){setBusy(true);setError('');try{const value=await workflowRequest('/admin/workspace-reset');receive(value);setDesignerId(value.designers.some(d=>String(d.id)===designerId)?designerId:value.designers.length===1?String(value.designers[0].id):'');setConfirmation('');setRequestId(crypto.randomUUID());setDialog(true)}catch(e){setError(e.message)}finally{setBusy(false)}}
  async function schedule(event){event.preventDefault();setBusy(true);setError('');try{receive(await workflowRequest('/admin/workspace-reset',{method:'POST',body:{confirmation,expected_fingerprint:state.fingerprint,request_id:requestId,keep_admin_id:state.suggested_admin_id,keep_designer_id:Number(designerId)}}));setDialog(false)}catch(e){setError(e.message)}finally{setBusy(false)}}
  async function cancel(){setBusy(true);setError('');try{receive(await workflowRequest(`/admin/workspace-reset/${state.id}/cancel`,{method:'POST'}))}catch(e){setError(e.message)}finally{setBusy(false)}}
  const remaining=state?.due_at?Math.max(0,Math.ceil((Date.parse(state.due_at)-(clock.server+tick-clock.received))/1000)):0
  const countdown=`${Math.floor(remaining/60)}:${String(remaining%60).padStart(2,'0')}`
  const admin=state?.administrators?.find(a=>a.id===state.suggested_admin_id)
  return <section className="workspace-reset" aria-labelledby="workspace-reset-title"><header><AlertTriangle size={20}/><div><h3 id="workspace-reset-title">Reset projects &amp; extra accounts</h3><p>Remove projects from active lists and keep one Admin and one Designer account. Floorplans, original files, BOMs, settings, prices, pairings, assemblies and legends are preserved.</p></div></header>
    {state&&active(state.phase)?<div className="workspace-reset-pending"><strong>{state.phase==='pending'?`Cleanup starts in ${countdown}`:'Applying cleanup…'}</strong><p>{state.phase==='pending'?'You can cancel before cleanup starts. Editing is paused; the countdown continues if this page closes.':'A private database backup is created first. Project files are kept.'}</p>{state.phase==='pending'&&<Button variant="outline" disabled={busy} onClick={cancel}>Cancel cleanup</Button>}</div>:<><Button variant="outline" disabled={busy||!state} onClick={open}><Archive size={15}/>Reset projects &amp; accounts</Button>{state?.phase==='completed'&&<p role="status">Cleanup complete. Projects archived, selected accounts retained, floorplans and BOMs preserved.</p>}{state?.phase==='cancelled'&&<p role="status">Cleanup cancelled. Your workspace data is kept.</p>}{state?.phase==='failed'&&<p role="alert">{state.detail || 'The previous reset failed. Your workspace data is retained; review a new cleanup below.'}</p>}</>}
    {error&&!dialog&&<p role="alert">{error}</p>}
    {dialog&&<AccountDialog title="Reset projects and extra accounts?" description="There is a five-minute cancellation period. A database backup is required before changes begin." busy={busy} onClose={()=>setDialog(false)}><form className="workspace-reset-form" onSubmit={schedule}>
      <p><strong>{state.counts.projects} active projects</strong> will be archived. Their floorplans, BOMs, estimates and saved versions stay in history.</p>
      <label>Admin account to keep<input readOnly value={admin?`${admin.label} · ${admin.email || ''}`:'Signed-in Admin'}/></label>
      <label>Designer account to keep<select required disabled={busy} value={designerId} onChange={e=>setDesignerId(e.target.value)}><option value="" disabled>Choose a Designer</option>{state.designers.map(d=><option key={d.id} value={d.id}>{d.label} · {d.email || ''}</option>)}</select></label>
      <p>All other users, including other Admins, lose sign-in access. Passwords, Google links and recovery information are removed. Anonymous author IDs remain only where saved history requires them.</p>
      <label className="workspace-reset-check"><input type="checkbox" required disabled={busy}/>Keep only these two accounts and archive active projects.</label>
      <label>Type <strong>RESET WORKSPACE ACCESS</strong><input value={confirmation} onChange={e=>setConfirmation(e.target.value)} required autoComplete="off" disabled={busy} spellCheck="false"/></label>
      {error&&<p role="alert">{error}</p>}<footer><Button type="button" variant="outline" disabled={busy} onClick={()=>setDialog(false)}>Keep current workspace</Button><Button type="submit" disabled={busy||!designerId||confirmation!=='RESET WORKSPACE ACCESS'}>{busy?'Scheduling…':'Start 5-minute countdown'}</Button></footer>
    </form></AccountDialog>}
  </section>
}
