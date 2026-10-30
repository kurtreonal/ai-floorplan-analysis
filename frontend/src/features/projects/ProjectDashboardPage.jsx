import { useEffect, useState } from 'react'

import { listProjects, ProjectApiError } from '../../api/projects.js'
import { getProjectHref } from '../../routes/projectRoutes.js'
import { CreateProjectForm } from './CreateProjectForm.jsx'
import { AdminWorkspace } from '../admin/AdminWorkspace.jsx'
import { Search, FolderOpen, SlidersHorizontal } from 'lucide-react'
import { Input } from '../../components/ui/input.jsx'
import { compareLabels } from '../../utils/listOrder.js'
import { ProjectOverview } from './ProjectOverview.jsx'
import { Button } from '../../components/ui/button.jsx'
import {ProjectAge} from './ProjectAge.jsx'
import {ClientDirectoryTable} from './ClientDirectoryTable.jsx'


function formatStatus(status) {
  return status.replaceAll('_', ' ')
}

function formatTimestamp(value) {
  const timestamp = new Date(value)
  if (Number.isNaN(timestamp.getTime())) return 'Unavailable'
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(timestamp)
}

function getListErrorMessage(error) {
  if (error instanceof ProjectApiError) {
    if (error.status === 401) {
      window.location.replace('#/signin?reason=session-expired')
      return null
    }
    if (error.status === 403) return 'Your account is not allowed to view projects.'
    if (error.status === 503) return 'Projects are temporarily unavailable.'
  }
  return 'We could not load projects. Please try again.'
}

export function ProjectDashboardPage({ session, initialSection, clientFilter = null }) {
  const [projects, setProjects] = useState([])
  const [loadState, setLoadState] = useState('loading')
  const [error, setError] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sort, setSort] = useState('name')
  const isDesigner = session.user.role === 'DESIGNER'
  const administrationOnly = session.user.role === 'ADMIN' && !initialSection
  const section = clientFilter?'projects':'clients'
  const clients = [...new Set(projects.map(p => p.client_id ? `id:${p.client_id}` : `name:${p.client_name || 'Unassigned client'}`))].map(key => {
    const list = projects.filter(p => (p.client_id ? `id:${p.client_id}` : `name:${p.client_name || 'Unassigned client'}`) === key)
    return { key, name: list[0]?.client_name || 'Unassigned client', projects: list }
  })
  const filteredProjects = projects.filter((project) =>
    (!clientFilter || (project.client_id ? `id:${project.client_id}` : `name:${project.client_name || 'Unassigned client'}`) === clientFilter)
    && (statusFilter === 'all' || project.status === statusFilter)
    && [project.name, project.client_name, project.location, String(project.id)].filter(Boolean).join(' ').toLowerCase().includes(search.trim().toLowerCase()),
  ).sort((a, b) => (sort === 'name' ? compareLabels(a.name,b.name) : new Date(b.updated_at) - new Date(a.updated_at)) || compareLabels(a.id,b.id))

  useEffect(() => {
    const controller = new AbortController()

    async function loadProjectList() {
      setProjects([])
      setLoadState('loading')
      setError(null)
      try {
        const projectList = await listProjects({ signal: controller.signal })
        if (controller.signal.aborted) return
        setProjects(projectList)
        setLoadState('ready')
      } catch (requestError) {
        if (requestError.name !== 'AbortError') {
          setError(getListErrorMessage(requestError))
          setLoadState('error')
        }
      }
    }

    loadProjectList()
    return () => controller.abort()
  }, [refreshKey, session.user.id, session.user.role])

  function handleCreated(project) {
    setProjects((current) => [project, ...current.filter((item) => item.id !== project.id)])
    setLoadState('ready')
  }

  return (
    <>
      {!administrationOnly && <section className="project-dashboard-hero">
        <div>
          <span className="project-kicker mono">{isDesigner ? 'PROJECT CONTROL':'VED ADMIN'}</span>
          <h1>{clientFilter?'Client projects':'Clients & projects'}</h1>
          <p>{isDesigner ? 'Choose a client, open an assigned project, then continue to its floorplans.':'Manage clients, assign projects and publish approved work.'}</p>
        </div>
        <div className="project-dashboard-count mono">
          <strong>{loadState === 'ready' ? initialSection === 'clients' ? clients.length : projects.length : '—'}</strong>
          <span>{initialSection === 'clients' ? 'CLIENTS' : 'PROJECTS'}</span>
        </div>
      </section>}

      {administrationOnly && <><AdminWorkspace /><p><a className="project-open-link" href="#/app/clients">Open clients & projects →</a></p></>}
      {!administrationOnly && <>
      {!isDesigner && <details className="studio-create-project"><summary><FolderOpen size={18} aria-hidden="true" />Create a project<span>Client · project details · designer assignment</span></summary><CreateProjectForm onCreated={handleCreated} /></details>}
      {(!initialSection || !isDesigner) && loadState === 'ready' && <ProjectOverview projects={projects}/>}
      {section==='clients' && <label className="studio-search"><Search size={18} aria-hidden="true"/><Input aria-label="Search clients and projects" placeholder="Search clients, projects or locations…" value={search} onChange={event=>setSearch(event.target.value)}/></label>}
      {section === 'clients' && loadState === 'loading' && <p role="status">Loading assigned clients…</p>}
      {section === 'clients' && loadState === 'error' && <div role="alert"><p>{error}</p><Button variant="outline" onClick={() => setRefreshKey(key => key + 1)}>Retry loading clients</Button></div>}
      {section === 'clients' && loadState==='ready' && <ClientDirectoryTable clients={clients} search={search} canDelete={session.user.role==='ADMIN'}/> }

      <section hidden={section !== 'projects'} className="project-list-panel" aria-labelledby="project-list-title">
        {clientFilter && <nav className="workflow-steps" aria-label="Project hierarchy"><a href="#/app/clients">Clients</a><span>›</span><span>{clients.find(x => x.key === clientFilter)?.name}</span><span>› Projects</span></nav>}
        <div className="project-section-heading project-list-heading">
          <div>
            <span className="project-kicker mono">WORKSPACES</span>
            <h2 id="project-list-title">Available projects</h2>
          </div>
          {loadState === 'error' && (
            <button className="btn btn-outline-dark" type="button" onClick={() => setRefreshKey((key) => key + 1)}>
              Retry
            </button>
          )}
        </div>

        <div className="studio-project-filters">
          <label className="studio-search"><Search size={18} aria-hidden="true" /><Input aria-label="Search projects" placeholder="Search project, client or location…" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
          <label><SlidersHorizontal size={16} aria-hidden="true" /><span className="sr-only">Project status</span><select aria-label="Project status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option>{[...new Set(projects.map((project) => project.status))].sort().map((status) => <option key={status} value={status}>{formatStatus(status)}</option>)}</select></label>
          <label><span className="sr-only">Sort projects</span><select aria-label="Sort projects" value={sort} onChange={(event) => setSort(event.target.value)}><option value="updated">Recently updated</option><option value="name">Project name</option></select></label>
          {loadState === 'ready' && <span className="mono">{filteredProjects.length} / {projects.length} projects</span>}
        </div>

        {loadState === 'loading' && (
          <div className="project-state" role="status" aria-live="polite">
            <span className="auth-spinner" aria-hidden="true" />
            Loading projects…
          </div>
        )}
        {loadState === 'error' && <div className="project-state project-state-error" role="alert">{error}</div>}
        {loadState === 'ready' && projects.length === 0 && (
          <div className="project-empty-state">
            <h3>No projects yet.</h3>
            <p>{isDesigner ? 'Admin will assign projects to your account. They will appear here when ready.' : 'Create a client account and assign a designer to start a project.'}</p>
          </div>
        )}
        {loadState === 'ready' && projects.length > 0 && (
          <div className="studio-table-scroll">
          <table className="studio-project-table">
            <caption className="sr-only">Projects — open a project to manage its floors and plans</caption>
            <thead><tr><th scope="col">Project</th><th scope="col">Client</th><th scope="col">Location</th><th scope="col">Status</th><th scope="col">Updated</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
            {filteredProjects.map((project) => (
              <tr key={project.id}>
                <th scope="row"><h3>{project.name} <ProjectAge createdAt={project.created_at}/></h3><small className="mono">PRJ-{String(project.id).padStart(4, '0')}</small></th>
                <td>{project.client_name || 'Not specified'}</td><td>{project.location || 'Not specified'}</td>
                <td><span className="project-status mono">{project.intake_status==='pending_admin'?'Admin review':formatStatus(project.status)}</span></td>
                <td>{formatTimestamp(project.updated_at)}</td>
                <td>
                <a className="project-open-link" href={getProjectHref(project.id)} aria-label={`Open ${project.name}`}>
                  Open project <span aria-hidden="true">→</span>
                </a>
                </td>
              </tr>
            ))}
            </tbody>
          </table>
          </div>
        )}
        {loadState === 'ready' && projects.length > 0 && filteredProjects.length === 0 && <div className="project-empty-state"><h3>No matching projects.</h3><p>Try another search or status filter.</p></div>}
      </section>
      </>}
    </>
  )
}
