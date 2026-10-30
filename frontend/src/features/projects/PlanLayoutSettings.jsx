import {useEffect,useState} from 'react'
import {workflowRequest} from '../../api/clientWorkflow.js'
import {Button} from '../../components/ui/button.jsx'
import {LayoutTypeChoices} from './LayoutTypeChoices.jsx'
import {layoutValues} from './projectIntake.js'

export function PlanLayoutSettings({projectId,planId,canEdit,onSaved}) {
  const [record,setRecord]=useState(null),[layout,setLayout]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  const path=`/projects/${projectId}/floor-plans/${planId}/layout-type`
  useEffect(()=>{const request=new AbortController();workflowRequest(path,{signal:request.signal}).then(value=>{setRecord(value);setLayout(value.layout_type || '')}).catch(e=>{if(!request.signal.aborted)setError(e.message)});return()=>request.abort()},[path])
  async function save(event){event.preventDefault();setBusy(true);setError('')
    try {const saved=await workflowRequest(path,{method:'PUT',body:{request_id:crypto.randomUUID(),expected_version:record.revision,layout_type:layout}});setRecord({layout_type:layout,revision:saved.version_number});onSaved?.()}
    catch(e){setError(e.message)}finally{setBusy(false)}}
  return <form className="plan-layout-settings" onSubmit={save}><LayoutTypeChoices value={layout} disabled={!canEdit || !record || busy} onChange={setLayout}/><small>Sets automatic material choices for this plan. Your drawing and saved estimates stay unchanged.</small>{canEdit && <Button type="submit" variant="outline" disabled={!record || busy || !layoutValues(layout).length || JSON.stringify(layoutValues(layout))===JSON.stringify(layoutValues(record.layout_type))}>{busy?'Saving…':'Save layout types'}</Button>}{error && <p role="alert">{error}</p>}</form>
}
