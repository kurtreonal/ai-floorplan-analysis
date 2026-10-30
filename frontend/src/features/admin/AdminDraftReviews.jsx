import { useEffect, useState } from 'react'
import { ArrowUpRight, Check, MessageSquare, RotateCcw } from 'lucide-react'
import { workflowRequest } from '../../api/clientWorkflow.js'
import { Button } from '../../components/ui/button.jsx'
import { AccountDialog } from '../settings/AccountDialog.jsx'
import './reviewDecisions.css'

export function AdminDraftReviews() {
  const [rows,setRows]=useState([]),[error,setError]=useState(''),[busy,setBusy]=useState(false),[refresh,setRefresh]=useState(0)
  const [loading,setLoading]=useState(true),[filter,setFilter]=useState('submitted'),[decision,setDecision]=useState(null),[note,setNote]=useState(''),[message,setMessage]=useState('')
  useEffect(()=>{const c=new AbortController();workflowRequest('/admin/draft-submissions',{signal:c.signal}).then(result=>{if(!c.signal.aborted)setRows(result)}).catch(e=>{if(!c.signal.aborted)setError(e.message)}).finally(()=>{if(!c.signal.aborted)setLoading(false)});return()=>c.abort()},[refresh])
  function open(row,approve){setError('');setMessage('');setNote('');setDecision({row,approve})}
  async function decide(event){
    event.preventDefault();if(!note.trim()||busy)return
    setBusy(true);setError('')
    try{
      await workflowRequest(`/admin/draft-submissions/${decision.row.review_id}`,{method:'POST',body:{approve:decision.approve,note:note.trim(),expected_action_id:decision.row.action_id}})
      setMessage(decision.approve?'Proposal approved and published to the Client.':'Proposal returned to the Designer with your comment.')
      setDecision(null);setLoading(true);setRefresh(x=>x+1)
    }catch(e){setError(e.message)}finally{setBusy(false)}
  }
  const visible=rows.filter(row=>row.status===filter)
  return <section className="workflow-panel admin-proposal-reviews">
    <header className="account-section-heading"><div><h2>Proposal review</h2><p>Review saved proposals and send your decision to the Designer.</p></div><Button variant="outline" disabled={loading||busy} onClick={()=>{setLoading(true);setError('');setRefresh(x=>x+1)}}>Refresh</Button></header>
    <div className="proposal-filters" role="group" aria-label="Proposal status">{[['submitted','Awaiting review'],['approved','Approved']].map(([value,label])=><button key={value} type="button" aria-pressed={filter===value} onClick={()=>setFilter(value)}>{label}<span>{rows.filter(row=>row.status===value).length}</span></button>)}</div>
    {error&&!decision&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    <div className="studio-table-scroll"><table className="studio-project-table"><thead><tr><th>Project / floor</th><th>Plan</th><th>Status / comment</th><th>Workspace</th><th>Decision</th></tr></thead><tbody>{visible.map(row=><tr key={row.review_id}>
      <td><strong>{row.project_name}</strong><small>{row.floor_name}</small></td>
      <td>Plan {row.floor_plan_id}<small>Saved revision {row.revision_number}</small>{row.latest_revision_number!==row.revision_number&&<small>Newer workspace revision: {row.latest_revision_number}</small>}</td>
      <td><span className={`proposal-status is-${row.status}`}>{row.status==='approved'?'Approved':'Awaiting review'}</span>{row.message&&row.status==='approved'&&<details className="proposal-comment"><summary><MessageSquare size={13}/>View comment</summary><p>{row.message}</p></details>}</td>
      <td><a className="proposal-open" href={`#/app/projects/${row.project_id}/floors/${row.floor_id}/floor-plans/${row.floor_plan_id}/interpretation/${row.processing_job_id}`}><ArrowUpRight size={15}/>Open workspace</a></td>
      <td><div className="proposal-actions">{row.status==='submitted'&&<Button size="sm" disabled={busy||loading} onClick={()=>open(row,true)}><Check size={14}/>Approve</Button>}<Button size="sm" disabled={busy||loading} variant="outline" onClick={()=>open(row,false)}><RotateCcw size={14}/>{row.status==='approved'?'Unapprove':'Return'}</Button></div></td>
    </tr>)}</tbody></table></div>
    {loading&&<p role="status">Loading proposals…</p>}{!loading&&!visible.length&&<p>{filter==='approved'?'No approved proposals.':'No proposals awaiting review. Returned proposals are with their Designer.'}</p>}
    {decision&&<AccountDialog title={decision.approve?'Approve proposal':'Return to Designer'} description={decision.approve?'The saved plan and its captured BOM will be available to the Client.':'This plan leaves the review queue and returns to the Designer. An approved plan will also be removed from Client access.'} busy={busy} onClose={()=>{setDecision(null);setError('')}}>
      <form className="proposal-decision-form" onSubmit={decide}><p><strong>{decision.row.project_name}</strong> · Plan {decision.row.floor_plan_id} · Revision {decision.row.revision_number}</p>
        <label htmlFor="proposal-decision-comment">Comment for the Designer <span>Required</span></label><textarea id="proposal-decision-comment" required maxLength={500} rows={5} value={note} onChange={event=>setNote(event.target.value)} placeholder={decision.approve?'Summarize your approval or any notes for the Designer.':'Describe what the Designer needs to change.'} disabled={busy}/><small>{note.length}/500</small>
        {error&&<p role="alert">{error}</p>}<div className="proposal-dialog-actions"><Button type="button" variant="outline" disabled={busy} onClick={()=>{setDecision(null);setError('')}}>Cancel</Button><Button type="submit" disabled={busy||!note.trim()}>{busy?'Saving…':decision.approve?'Approve & send comment':'Return & send comment'}</Button></div>
      </form>
    </AccountDialog>}
  </section>
}
