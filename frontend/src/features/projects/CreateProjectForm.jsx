import { useEffect, useRef, useState } from 'react'

import { createProject, ProjectApiError } from '../../api/projects.js'
import { getProjectHref } from '../../routes/projectRoutes.js'
import { ProjectIntakeFields } from './ProjectIntakeFields.jsx'
import { intakePayload, intakeValues } from './projectIntake.js'
import { workflowRequest } from '../../api/clientWorkflow.js'


const INITIAL_VALUES = intakeValues()

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
  const [accounts, setAccounts] = useState([])
  useEffect(() => { const c = new AbortController(); const load = () => workflowRequest('/admin/accounts', { signal: c.signal }).then(setAccounts).catch(e => { if (e.name !== 'AbortError') setError(e.message) }); load(); window.addEventListener('ved:accounts-changed', load); return () => { c.abort(); window.removeEventListener('ved:accounts-changed', load) } }, [])

  useEffect(() => () => requestController.current?.abort(), [])

  function updateField(event) {
    const { name, value } = event.target
    setValues((current) => ({ ...current, [name]: value,
      ...(name === 'serviceType' && value !== 'other' ? { serviceTypeOther: '' } : {}) }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const selections = new FormData(event.currentTarget)
    const projectData = { ...intakePayload(values), client_id: Number(selections.get('client_id')), designer_id: Number(selections.get('designer_id')) }

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
        <p>Start with the project details. A blueprint is not required.</p>
      </div>

      <form className="project-form" onSubmit={handleSubmit}>
        <label>Client account<select name="client_id" required disabled={isSubmitting}><option value="">Choose a client</option>{accounts.filter(x => x.role === 'CLIENT' && !x.disabled && x.username).map(x => <option key={x.id} value={x.id}>{x.label} · {x.username}</option>)}</select></label>
        <label>Assigned designer<select name="designer_id" required disabled={isSubmitting}><option value="">Choose a designer</option>{accounts.filter(x => x.role === 'DESIGNER' && !x.disabled && x.username).map(x => <option key={x.id} value={x.id}>{x.label} · #{x.id}</option>)}</select><small>{accounts.filter(x => x.role === 'DESIGNER' && !x.disabled && x.username).length} available designers. Set up new users in Admin settings → Users.</small></label>
        <ProjectIntakeFields values={values} onChange={updateField} disabled={isSubmitting} hideClient />

        {error && <div className="project-alert project-alert-error" role="alert">{error}</div>}
        {createdProject && (
          <div className="project-alert project-alert-success" role="status">
            Project created. <a href={getProjectHref(createdProject.id)}>Open {createdProject.name}</a>
            {createdProject.blueprint_availability === 'available_now' && <span> · <a href={getProjectHref(createdProject.id)}>Continue to floors &amp; upload</a></span>}
          </div>
        )}

        <button className="btn btn-accent project-submit" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Creating project…' : 'Create project'}
        </button>
      </form>
    </section>
  )
}
