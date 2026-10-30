import {useState} from 'react'
import {workflowRequest} from '../../api/clientWorkflow.js'
import {Button} from '../../components/ui/button.jsx'

export function PlanNameEditor({projectId,item,onSaved,floor=false}) {
  const current=floor?item.name:item.display_name
  const [name,setName]=useState(current || ''),[busy,setBusy]=useState(false),[error,setError]=useState('')
  async function save(event){event.preventDefault();setBusy(true);setError('')
    try{await workflowRequest(`/projects/${projectId}/${floor?'floors':'floor-plans'}/${item.id}${floor?'':'/name'}`,{method:'PATCH',body:{name:name.trim(),expected_name:current || null}});onSaved(name.trim())}catch(e){setError(e.message)}finally{setBusy(false)}}
  return <details className="plan-name-editor"><summary>{floor?'Rename floor':current?'Rename plan':'Name this plan'}</summary><form onSubmit={save}><label>{floor?'Floor name':'Floor-plan name'}<input required maxLength={100} value={name} onChange={e=>setName(e.target.value)} disabled={busy}/></label><Button variant="outline" type="submit" disabled={busy}>{busy?'Saving…':'Save name'}</Button>{error && <p role="alert">{error}</p>}</form></details>
}
