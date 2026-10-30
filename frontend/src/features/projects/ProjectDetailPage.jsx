import { useEffect, useRef, useState } from 'react'

import { fetchProject, deleteProject, ProjectApiError } from '../../api/projects.js'
import { ProjectFloorUploadPanel } from './ProjectFloorUploadPanel.jsx'
import { getEstimateHref } from '../../routes/projectRoutes.js'
import { Button } from '../../components/ui/button.jsx'
import { Calculator } from 'lucide-react'
import {ProjectDetailsTable} from './ProjectDetailsTable.jsx'
import { ProjectIntakeEditor } from './ProjectIntakeEditor.jsx'
import { AdminProjectWorkflow } from '../admin/AdminProjectWorkflow.jsx'


function formatTimestamp(value) {
  const timestamp = new Date(value)
  if (Number.isNaN(timestamp.getTime())) return 'Unavailable'
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'long',
    timeStyle: 'short',
  }).format(timestamp)
}

function getDetailError(error) {
  if (error instanceof ProjectApiError) {
    if (error.status === 401) {
      window.location.replace('#/signin?reason=session-expired')
      return null
    }
    if (error.status === 403) return 'You do not have access to this project.'
    if (error.status === 404) return 'The requested project was not found.'
    if (error.status === 422) return 'The project address is invalid.'
    if (error.status === 503) return 'Project details are temporarily unavailable.'
  }
  return 'We could not load this project. Please try again.'
}

export function ProjectDetailPage({ projectId, session }) {
  const [project, setProject] = useState(null)
  const [loadState, setLoadState] = useState(projectId ? 'loading' : 'invalid')
  const [error, setError] = useState(projectId ? null : 'The project address is invalid.')
  const [refreshKey, setRefreshKey] = useState(0)
  const uploadPanel = useRef(null)
  const [deleteOpen, setDeleteOpen] = useState(false), [deleting, setDeleting] = useState(false), [deleteError, setDeleteError] = useState('')
  async function removeProject() {
    setDeleting(true); setDeleteError('')
    try { await deleteProject(projectId); window.location.assign('#/app') } catch { setDeleteError('The project could not be deleted. Try again.'); setDeleting(false) }
  }

  useEffect(() => {
    if (!projectId) return undefined

    const controller = new AbortController()

    async function loadProject() {
      setLoadState('loading')
      setError(null)
      try {
        const projectData = await fetchProject(projectId, { signal: controller.signal })
        if (controller.signal.aborted) return
        setProject(projectData)
        setLoadState('ready')
      } catch (requestError) {
        if (requestError.name !== 'AbortError') {
          setError(getDetailError(requestError))
          setLoadState('error')
        }
      }
    }

    loadProject()
    return () => controller.abort()
  }, [projectId, refreshKey])

  if (loadState === 'loading') {
    return (
      <div className="project-detail-state" role="status" aria-live="polite">
        <span className="auth-spinner" aria-hidden="true" />
        Loading project details…
      </div>
    )
  }

  if (loadState === 'error' || loadState === 'invalid') {
    return (
      <section className="project-detail-error" aria-labelledby="project-detail-error-title">
        <span className="project-kicker mono">PROJECT UNAVAILABLE</span>
        <h1 id="project-detail-error-title">This workspace could not be opened.</h1>
        <p role="alert">{error}</p>
        <div className="project-detail-actions">
          {projectId && (
            <button className="btn btn-accent" type="button" onClick={() => setRefreshKey((key) => key + 1)}>
              Try again
            </button>
          )}
          <a className="btn btn-outline-dark" href="#/app">Back to dashboard</a>
        </div>
      </section>
    )
  }

  return (
    <article className="project-detail" aria-labelledby="project-detail-title">
      <a className="project-back-link" href="#/app/clients">← Clients &amp; projects</a>
      <nav className="workflow-steps" aria-label="Project hierarchy"><a href="#/app/clients">Clients</a><a href={`#/app/clients/${encodeURIComponent(project.client_id?`id:${project.client_id}`:`name:${project.client_name || 'Unassigned client'}`)}/projects`}>› {project.client_name || 'Unassigned client'}</a><span>› {project.name}</span><span>› Floor plans</span></nav>
      <div className="project-detail-heading">
        <div>
          <span className="project-kicker mono">PROJECT METADATA</span>
          <h1 id="project-detail-title">{project.name}</h1>
        </div>
        <div className="studio-detail-actions"><span className="project-status project-detail-status mono">
          {project.status.replaceAll('_', ' ')}
        </span></div>
      </div>
      <p className="project-detail-intro">
        Review the project metadata, organize its floors, and upload original floor-plan files.
      </p>
      <ProjectDetailsTable project={project} formatTimestamp={formatTimestamp}/>
      {session?.user?.role === 'ADMIN' && <><ProjectIntakeEditor key={project.id} project={project} onSaved={setProject} onReload={() => setRefreshKey(key => key + 1)} /><AdminProjectWorkflow project={project} onChanged={() => setRefreshKey(key => key + 1)}/>
        <div className="workflow-panel"><Button variant="outline" className="workflow-danger" onClick={() => setDeleteOpen(!deleteOpen)}>Delete project</Button>
        {deleteOpen && <div role="alert"><p>Remove “{project.name}” from active projects? Original files and saved estimates will be retained.</p><Button disabled={deleting} onClick={removeProject}>{deleting ? 'Deleting…' : 'Confirm delete'}</Button> <Button variant="outline" onClick={() => setDeleteOpen(false)}>Cancel</Button></div>}{deleteError && <p role="alert">{deleteError}</p>}</div></>}
      {session?.user?.role === 'DESIGNER' && project.blueprint_availability === 'available_now' && <Button variant="outline" onClick={() => {
        uploadPanel.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }); uploadPanel.current?.focus({ preventScroll: true })
      }}>Add floors &amp; upload blueprint</Button>}
      {session && <div ref={uploadPanel} tabIndex={-1} aria-label="Floors and original uploads"><ProjectFloorUploadPanel projectId={project.id} session={session} /></div>}
      <footer className="project-estimate-footer"><div><h2>Overall project estimate</h2><p>Combine all floors and plans. Each floor plan keeps its own BOM.</p></div><Button asChild><a href={getEstimateHref(project.id)}><Calculator aria-hidden="true"/>Overall cost estimation</a></Button></footer>
    </article>
  )
}
