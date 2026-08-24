import { useEffect, useState } from 'react'

import { listProjects, ProjectApiError } from '../../api/projects.js'
import { getProjectHref } from '../../routes/projectRoutes.js'
import { CreateProjectForm } from './CreateProjectForm.jsx'


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

export function ProjectDashboardPage({ session }) {
  const [projects, setProjects] = useState([])
  const [loadState, setLoadState] = useState('loading')
  const [error, setError] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const isDesigner = session.user.role === 'DESIGNER'

  useEffect(() => {
    const controller = new AbortController()

    async function loadProjectList() {
      setLoadState('loading')
      setError(null)
      try {
        const projectList = await listProjects({ signal: controller.signal })
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
  }, [refreshKey])

  function handleCreated(project) {
    setProjects((current) => [project, ...current.filter((item) => item.id !== project.id)])
    setLoadState('ready')
  }

  return (
    <>
      <section className="project-dashboard-hero">
        <div>
          <span className="project-kicker mono">PROJECT CONTROL</span>
          <h1>Electrical planning projects</h1>
          <p>Open an existing workspace or create a new project for VED analysis.</p>
        </div>
        <div className="project-dashboard-count mono">
          <strong>{loadState === 'ready' ? projects.length : '—'}</strong>
          <span>AVAILABLE</span>
        </div>
      </section>

      {isDesigner && <CreateProjectForm onCreated={handleCreated} />}

      <section className="project-list-panel" aria-labelledby="project-list-title">
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
            <p>{isDesigner ? 'Use the create-project form to start your first workspace.' : 'No projects are currently available for review.'}</p>
          </div>
        )}
        {loadState === 'ready' && projects.length > 0 && (
          <div className="project-grid">
            {projects.map((project) => (
              <article className="project-card" key={project.id}>
                <div className="project-card-topline">
                  <span className="project-status mono">{formatStatus(project.status)}</span>
                  <span className="project-number mono">PRJ-{String(project.id).padStart(4, '0')}</span>
                </div>
                <h3>{project.name}</h3>
                <dl>
                  <div><dt>Client</dt><dd>{project.client_name || 'Not specified'}</dd></div>
                  <div><dt>Location</dt><dd>{project.location || 'Not specified'}</dd></div>
                  <div><dt>Updated</dt><dd>{formatTimestamp(project.updated_at)}</dd></div>
                </dl>
                <a className="project-open-link" href={getProjectHref(project.id)} aria-label={`Open ${project.name}`}>
                  Open project <span aria-hidden="true">→</span>
                </a>
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  )
}
