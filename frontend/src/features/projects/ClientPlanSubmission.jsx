import {LayoutTypeChoices} from './LayoutTypeChoices.jsx'
import {useEffect,useRef,useState} from 'react'
import {workflowRequest} from '../../api/clientWorkflow.js'
import {Button} from '../../components/ui/button.jsx'
import {ProjectIntakeFields} from './ProjectIntakeFields.jsx'
import {intakePayload,intakeValues} from './projectIntake.js'
import {FLOOR_PLAN_ACCEPT} from './FloorPlanUploadForm.jsx'

export function ClientPlanSubmission({project,onSubmitted,onClose}) {
  const [values,setValues]=useState(()=>intakeValues())
  const [designers,setDesigners]=useState([]),[floors,setFloors]=useState([])
  const [rows,setRows]=useState([{id:crypto.randomUUID(),floor:'',file:null,uploaded:false,layoutTypes:[]}])
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('')
  const [createdId,setCreatedId]=useState(project?.id || null)
  const submission=useRef({id:project?.id,requestId:crypto.randomUUID()})
  useEffect(()=>{const c=new AbortController();Promise.all([workflowRequest('/client/designers',{signal:c.signal}),project?workflowRequest(`/client/projects/${project.id}/files`,{signal:c.signal}):Promise.resolve([])])
    .then(([d,f])=>{setDesigners(d);setFloors(f)}).catch(e=>{if(e.name!=='AbortError')setError(e.message)});return()=>c.abort()},[project])
  function rowChange(id,changes){setRows(current=>current.map(row=>row.id===id?{...row,...changes}:row))}
  async function submit(event) {
    event.preventDefault();if(busy)return
    if(rows.some(row=>!row.file && !row.uploaded)){setError('Choose a file for each floor-plan row.');return}
    if(rows.some(row=>!row.uploaded && !row.layoutTypes?.length)){setError('Select the layout types included in each file.');return}
    setBusy(true);setError('');setNotice('')
    try {
      if(!submission.current.id){
        const data=new FormData(event.currentTarget)
        const result=await workflowRequest('/client/projects',{method:'POST',body:{...intakePayload(values),request_id:submission.current.requestId,preferred_designer_id:data.get('designer')?Number(data.get('designer')):null}})
        submission.current.id=result.id
        setCreatedId(result.id)
      }
      for(const row of rows.filter(row=>!row.uploaded)){
        const body=new FormData();body.append('file',row.file);body.append('request_id',row.id);if(row.floor)body.append('floor_id',row.floor);for(const type of row.layoutTypes)body.append('layout_types',type)
        await workflowRequest(`/client/projects/${submission.current.id}/floor-plans`,{method:'POST',body})
        rowChange(row.id,{uploaded:true})
      }
      setNotice('Floor plans sent to Admin. Your preferred designer will be considered during assignment.')
      onSubmitted?.()
    } catch(e){setError(`${e.message}${submission.current.id?' Your request and completed uploads are kept. Retry only the remaining files.':''}`)}finally{setBusy(false)}
  }
  return <section className="workflow-panel client-plan-submission" aria-labelledby="client-submission-title"><header className="account-section-heading"><div><h2 id="client-submission-title">{project?`Send plans · ${project.name}`:'Project details'}</h2><p>Admin reviews your request and assigns a designer.</p></div><Button variant="ghost" onClick={onClose} disabled={busy}>Back to projects</Button></header>
    <form onSubmit={submit}>
      {!project && <div className="project-form"><ProjectIntakeFields values={values} hideClient disabled={busy || Boolean(createdId)} onChange={event=>setValues(current=>({...current,[event.target.name]:event.target.value}))}/>
        <label>Preferred designer<select name="designer" disabled={busy || Boolean(createdId)}><option value="">Let Admin recommend a designer</option>{designers.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select><small>Preference only; Admin confirms the assignment.</small></label></div>}
      <div className="studio-table-scroll"><table className="studio-project-table"><caption>Floor-plan files</caption><thead><tr><th>Floor</th><th>Plan name</th><th>Layout types</th><th>File</th><th>Action</th></tr></thead><tbody>{rows.map((row,i)=><tr key={row.id}><td><select aria-label={`Floor for file ${i+1}`} value={row.floor} disabled={busy || row.uploaded} onChange={e=>rowChange(row.id,{floor:e.target.value})}><option value="">Add new floor</option>{floors.map(f=><option value={f.id} key={f.id}>{f.name}</option>)}</select></td><td><span className="project-status">Pending designer name</span></td><td><LayoutTypeChoices value={row.layoutTypes} onChange={layoutTypes=>rowChange(row.id,{layoutTypes})} disabled={busy || row.uploaded}/></td><td>{row.uploaded?<span>Sent · {row.file.name}</span>:<input aria-label={`Floor-plan file ${i+1}`} type="file" required accept={FLOOR_PLAN_ACCEPT} disabled={busy} onChange={e=>rowChange(row.id,{file:e.target.files[0] || null})}/>}</td><td><Button type="button" variant="ghost" disabled={busy || row.uploaded || rows.length===1} onClick={()=>setRows(current=>current.filter(r=>r.id!==row.id))}>Remove</Button></td></tr>)}</tbody></table></div>
      <div className="account-actions"><Button type="button" variant="outline" disabled={busy} onClick={()=>setRows(current=>[...current,{id:crypto.randomUUID(),floor:'',file:null,uploaded:false,layoutTypes:[]}])}>Add floor / plan</Button><Button type="submit" disabled={busy || rows.every(row=>row.uploaded)}>{busy?'Sending…':'Send to Admin'}</Button></div>
      {error && <p role="alert">{error}</p>}{notice && <p className="account-notice" role="status">{notice}</p>}
    </form>
  </section>
}
