import { useEffect, useRef, useState } from 'react'
import { updateProject } from '../../api/projects.js'
import { ProjectIntakeFields } from './ProjectIntakeFields.jsx'
import { intakePayload, intakeValues } from './projectIntake.js'

export function ProjectIntakeEditor({ project, onSaved, onReload }) {
  const [values, setValues] = useState(() => intakeValues(project))
  const [busy, setBusy] = useState(false)
  const [uncertain, setUncertain] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const request = useRef(null)
  const retry = useRef(null)
  const inFlight = useRef(false)
  useEffect(() => () => request.current?.abort(), [])
  function change(event) {
    const { name, value } = event.target
    setValues(current => ({ ...current, [name]: value, ...(name === 'serviceType' && value !== 'other' ? { serviceTypeOther: '' } : {}) }))
    setMessage('')
  }
  async function save(event) {
    event.preventDefault()
    if (inFlight.current) return
    const payload = retry.current || { ...intakePayload(values, true), expected_details_revision: project.details_revision }
    const controller = new AbortController(); request.current = controller
    inFlight.current = true; setBusy(true); setError(''); setMessage('')
    retry.current = payload
    try {
      const saved = await updateProject(project.id, payload, { signal: controller.signal })
      if (controller.signal.aborted) return
      retry.current = null; setUncertain(false); setValues(intakeValues(saved)); setMessage('Project details saved.'); onSaved(saved)
    } catch (failure) {
      if (controller.signal.aborted) return
      if (failure.status === 401) window.location.replace('#/signin?reason=session-expired')
      const unknown = !failure.status || failure.status >= 500
      setUncertain(unknown)
      if (!unknown) retry.current = null
      setError(unknown ? 'Save result uncertain. Retry the same details, or discard edits and reload.'
        : failure.status === 409 ? 'Project details changed elsewhere. Your inputs are kept; reload to review the current version.'
          : failure.status === 422 ? 'Check the project details, including the Other description and date.' : 'Project details could not be saved.')
    } finally { inFlight.current = false; if (!controller.signal.aborted) setBusy(false) }
  }
  return <details className="project-intake-editor"><summary>Edit project details</summary>
    <form className="project-form" onSubmit={save}>
      <ProjectIntakeFields values={values} onChange={change} disabled={busy || uncertain} />
      <div className="project-form-wide project-detail-actions">
        <button className="btn btn-accent" type="submit" disabled={busy}>{busy ? 'Saving…' : uncertain ? 'Retry same details' : 'Save project details'}</button>
        <button className="btn btn-outline-dark" type="button" disabled={busy} onClick={onReload}>Discard edits &amp; reload</button>
      </div>
      {error && <p className="project-alert project-alert-error" role="alert">{error}</p>}
      {message && <p className="project-alert project-alert-success" role="status">{message}</p>}
    </form>
  </details>
}
