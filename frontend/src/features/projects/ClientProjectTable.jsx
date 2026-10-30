import {useState} from 'react'
import {Search} from 'lucide-react'
import {Button} from '../../components/ui/button.jsx'
import {ProjectAge} from './ProjectAge.jsx'

const money=(amount,currency='PHP')=>new Intl.NumberFormat(undefined,{style:'currency',currency}).format(Number(amount))
const stage=project=>project.intake_status==='pending_admin'?'review':project.approved?'approved':'design'
const stages={review:'Admin review',design:'Design in progress',approved:'Ready to view'}
function PublishedCost({project}){
  if(!project.approved_bom)return <span className="client-muted">Not published yet</span>
  const totals=Object.entries(project.approved_bom.totals || {})
  return <>{totals.length?totals.map(([currency,total])=><div key={currency}>{money(total,currency)}</div>):'Not priced yet'}<small>{project.approved_bom.incomplete?'Partial estimate':project.approved_bom.estimated?'Estimated total':'Published total'}</small></>
}
export function ClientProjectTable({projects,onOpen,onSubmit}){
  const [sort,setSort]=useState('recent'),[filter,setFilter]=useState('all'),[query,setQuery]=useState('')
  const rows=projects.filter(project=>(filter==='all' || stage(project)===filter) && `${project.name} ${project.location || ''}`.toLowerCase().includes(query.trim().toLowerCase())).sort((a,b)=>sort==='name'?a.name.localeCompare(b.name):Date.parse(b.created_at)-Date.parse(a.created_at))
  return <section className="client-directory client-project-list" aria-label="Your project list">
    <div className="client-project-toolbar"><label className="client-project-search"><Search size={18} aria-hidden="true"/><input type="search" aria-label="Search your projects" placeholder="Search projects or locations" value={query} onChange={event=>setQuery(event.target.value)}/></label><label>Status<select value={filter} onChange={event=>setFilter(event.target.value)}><option value="all">All projects</option><option value="review">Admin review</option><option value="design">Design in progress</option><option value="approved">Ready to view</option></select></label><label>Sort<select value={sort} onChange={event=>setSort(event.target.value)}><option value="recent">Newest first</option><option value="name">Project name</option></select></label></div>
    <div className="client-list-caption">{rows.length} {rows.length===1?'project':'projects'}</div>
    <div className="studio-table-scroll"><table className="studio-project-table client-project-table"><thead><tr><th>Project</th><th>Status</th><th>Budget</th><th>Published estimate</th><th>Action</th></tr></thead><tbody>{rows.map(project=><tr key={project.id}><th scope="row"><strong>{project.name}</strong><ProjectAge createdAt={project.created_at}/><small className="client-muted">{project.location || 'Location not provided'}</small><div className="client-project-mobile-info"><span className={`client-stage client-stage-${stage(project)}`}>{stages[stage(project)]}</span><small>Budget: {project.allocated_budget==null?'Not allocated':money(project.allocated_budget)}</small><div><small>Published estimate</small><PublishedCost project={project}/></div></div></th><td><span className={`client-stage client-stage-${stage(project)}`}>{stages[stage(project)]}</span></td><td>{project.allocated_budget==null?<span className="client-muted">Not allocated</span>:money(project.allocated_budget)}</td><td><PublishedCost project={project}/></td><td><div className="client-project-actions">{project.approved?<Button variant="outline" onClick={()=>onOpen(project.id)}>View project</Button>:<small className="client-muted">Available after Admin review</small>}{project.intake_status==='pending_admin' && <Button variant="outline" onClick={()=>onSubmit(project)}>Add files</Button>}</div></td></tr>)}{!rows.length && <tr><td colSpan={5}><div className="client-empty-state"><strong>{projects.length?'No matching projects':'Your projects will appear here'}</strong><p>{projects.length?'Try another search or status.':'Send a floor plan to start a project with VED.'}</p></div></td></tr>}</tbody></table></div>
  </section>
}
