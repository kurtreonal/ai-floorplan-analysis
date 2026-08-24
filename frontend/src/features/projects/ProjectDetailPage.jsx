import { useEffect, useState } from 'react'

import { fetchProject, ProjectApiError } from '../../api/projects.js'


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

export function ProjectDetailPage({ projectId }) {
  const [project, setProject] = useState(null)
  const [loadState, setLoadState] = useState(projectId ? 'loading' : 'invalid')
  const [error, setError] = useState(projectId ? null : 'The project address is invalid.')
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    if (!projectId) return undefined

    const controller = new AbortController()

    async function loadProject() {
      setLoadState('loading')
      setError(null)
      try {
        const projectData = await fetchProject(projectId, { signal: controller.signal })
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
      <a className="project-back-link" href="#/app">← Back to dashboard</a>
      <div className="project-detail-heading">
        <div>
          <span className="project-kicker mono">PROJECT METADATA</span>
          <h1 id="project-detail-title">{project.name}</h1>
        </div>
        <span className="project-status project-detail-status mono">
          {project.status.replaceAll('_', ' ')}
        </span>
      </div>
      <p className="project-detail-intro">
        Workspace metadata is ready. Floor plans and analysis tools will appear as their tickets are completed.
      </p>
      <dl className="project-detail-grid">
        <div><dt>Project ID</dt><dd>{project.id}</dd></div>
        <div><dt>Owner ID</dt><dd>{project.owner_id}</dd></div>
        <div><dt>Client</dt><dd>{project.client_name || 'Not specified'}</dd></div>
        <div><dt>Location</dt><dd>{project.location || 'Not specified'}</dd></div>
        <div><dt>Created</dt><dd>{formatTimestamp(project.created_at)}</dd></div>
        <div><dt>Last updated</dt><dd>{formatTimestamp(project.updated_at)}</dd></div>
      </dl>
    </article>
  )
}
