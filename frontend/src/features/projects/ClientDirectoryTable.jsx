import {useEffect,useState} from 'react'
import {compareLabels} from '../../utils/listOrder.js'
import {workflowRequest} from '../../api/clientWorkflow.js'
import {DeleteClientButton} from './DeleteClientButton.jsx'

export function ClientDirectoryTable({clients,search='',canDelete=false}) {
  const [sort,setSort]=useState('name')
  const [status,setStatus]=useState('all')
  const [removed,setRemoved]=useState([])
  const [activeClientIds,setActiveClientIds]=useState(null)
  useEffect(()=>{
    if(!canDelete)return
    const controller=new AbortController()
    const load=()=>workflowRequest('/admin/accounts',{signal:controller.signal}).then(accounts=>setActiveClientIds(accounts.filter(a=>a.role==='CLIENT' && !a.disabled).map(a=>a.id))).catch(()=>{})
    load();window.addEventListener('ved:accounts-changed',load)
    return ()=>{controller.abort();window.removeEventListener('ved:accounts-changed',load)}
  },[canDelete])
  const updated=client=>Math.max(0,...client.projects.map(p=>Date.parse(p.updated_at)||0))
  const visible=clients.filter(client=>!removed.includes(client.projects[0]?.client_id)
    && (!canDelete || activeClientIds===null || !client.projects[0]?.client_id || activeClientIds.includes(client.projects[0].client_id)) && client.projects.some(p=>
    [client.name,p.name,p.location].filter(Boolean).join(' ').toLowerCase().includes(search.trim().toLowerCase())
    && (status==='all' || (p.intake_status==='pending_admin')===(status==='review'))))
    .sort((a,b)=>(sort==='recent'?updated(b)-updated(a):sort==='projects'?b.projects.length-a.projects.length:compareLabels(a.name,b.name)) || compareLabels(a.name,b.name))
  return <section className="client-directory client-directory-table" aria-label="Client list">
    <div className="client-directory-controls"><span>{visible.length} clients</span><label>Status<select value={status} onChange={e=>setStatus(e.target.value)}><option value="all">All clients</option><option value="review">Awaiting Admin review</option><option value="assigned">Assigned projects</option></select></label><label>Sort by<select value={sort} onChange={e=>setSort(e.target.value)}><option value="name">Client name</option><option value="recent">Recently updated</option><option value="projects">Most projects</option></select></label></div>
    <div className="studio-table-scroll"><table className="studio-project-table"><caption className="sr-only">Clients and assigned projects. Open a client to see their projects.</caption><thead><tr><th>Client</th><th>Projects</th><th>Status</th><th>Updated</th>{canDelete && <th>Delete</th>}</tr></thead><tbody>
      {visible.map(client=><tr key={client.key}><th scope="row"><a href={`#/app/clients/${encodeURIComponent(client.key)}/projects`}>{client.name}</a><small className="client-directory-mobile-meta">{client.projects.length} {client.projects.length===1?'project':'projects'} · {client.projects.some(p=>p.intake_status==='pending_admin')?'Admin review':'Assigned'}</small></th><td>{client.projects.length}</td><td>{client.projects.some(p=>p.intake_status==='pending_admin')?'Admin review':'Assigned'}</td><td>{updated(client)?new Date(updated(client)).toLocaleDateString():'—'}</td>{canDelete && <td>{client.projects[0]?.client_id ? <DeleteClientButton clientId={client.projects[0].client_id} name={client.name} onDeleted={id=>setRemoved(current=>[...current,id])}/> : 'No account'}</td>}</tr>)}
      {!visible.length && <tr><td colSpan={canDelete?5:4}>No clients match these filters.</td></tr>}
    </tbody></table></div>
  </section>
}
