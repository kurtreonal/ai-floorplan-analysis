import { useEffect, useRef, useState } from 'react'

import { createProject, ProjectApiError } from '../../api/projects.js'
import { getProjectHref } from '../../routes/projectRoutes.js'


const INITIAL_VALUES = { name: '', clientName: '', location: '' }

function getCreateErrorMessage(error) {
  if (error instanceof ProjectApiError) {
    if (error.status === 401) {
      window.location.replace('#/signin?reason=session-expired')
      return null
    }
    if (error.status === 403) return 'Your account is not allowed to create projects.'
    if (error.status === 422) return 'Check the project details and try again.'
    if (error.status === 503) return 'Project creation is temporarily unavailable.'
  }
  return 'We could not create the project. Please try again.'
}

export function CreateProjectForm({ onCreated }) {
  const [values, setValues] = useState(INITIAL_VALUES)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [createdProject, setCreatedProject] = useState(null)
  const requestController = useRef(null)

  useEffect(() => () => requestController.current?.abort(), [])

  function updateField(event) {
    const { name, value } = event.target
    setValues((current) => ({ ...current, [name]: value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const projectData = {
      name: values.name.trim(),
      client_name: values.clientName.trim(),
      location: values.location.trim(),
    }

    if (!projectData.name) {
      setError('Project name is required.')
      return
    }

    requestController.current?.abort()
    requestController.current = new AbortController()
    setIsSubmitting(true)
    setError(null)
    setCreatedProject(null)

    try {
      const project = await createProject(projectData, {
        signal: requestController.current.signal,
      })
      setValues(INITIAL_VALUES)
      setCreatedProject(project)
      onCreated(project)
    } catch (requestError) {
      if (requestError.name !== 'AbortError') {
        setError(getCreateErrorMessage(requestError))
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="project-create-panel" aria-labelledby="create-project-title">
      <div className="project-section-heading">
        <span className="project-kicker mono">NEW PROJECT</span>
        <h2 id="create-project-title">Start a project workspace</h2>
        <p>Set the project metadata now. Floor plans and analysis are added in later stages.</p>
      </div>

      <form className="project-form" onSubmit={handleSubmit}>
        <label>
          <span>Project name</span>
          <input
            name="name"
            value={values.name}
            onChange={updateField}
            required
            maxLength={255}
            autoComplete="off"
            disabled={isSubmitting}
          />
        </label>
        <label>
          <span>Client name <small>Optional</small></span>
          <input
            name="clientName"
            value={values.clientName}
            onChange={updateField}
            maxLength={255}
            autoComplete="organization"
            disabled={isSubmitting}
          />
        </label>
        <label className="project-form-wide">
          <span>Location <small>Optional</small></span>
          <input
            name="location"
            value={values.location}
            onChange={updateField}
            maxLength={500}
            autoComplete="street-address"
            disabled={isSubmitting}
          />
        </label>

        {error && <div className="project-alert project-alert-error" role="alert">{error}</div>}
        {createdProject && (
          <div className="project-alert project-alert-success" role="status">
            Project created. <a href={getProjectHref(createdProject.id)}>Open {createdProject.name}</a>
          </div>
        )}

        <button className="btn btn-accent project-submit" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Creating project…' : 'Create project'}
        </button>
      </form>
    </section>
  )
}
