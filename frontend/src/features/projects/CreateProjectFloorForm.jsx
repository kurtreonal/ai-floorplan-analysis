import { useEffect, useRef, useState } from 'react'

import {
  createProjectFloor,
  ProjectFloorApiError,
} from '../../api/projectFloors.js'


function getCreationError(error) {
  if (error instanceof ProjectFloorApiError) {
    if (error.status === 401) {
      window.location.replace('#/signin?reason=session-expired')
      return null
    }
    if (error.status === 403) return 'You are not authorized to create project floors.'
    if (error.status === 404) return 'The selected project is no longer available.'
    if (error.status === 422) return 'Enter a floor name between 1 and 100 characters.'
    if (error.status === 503 || error.status === 0) {
      return 'The project-floor service is temporarily unavailable.'
    }
  }
  return 'The project floor could not be created. Please try again.'
}

export function CreateProjectFloorForm({ projectId, disabled = false, onCreated }) {
  const [name, setName] = useState('')
  const [error, setError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const submissionLocked = useRef(false)
  const activeController = useRef(null)

  useEffect(() => () => activeController.current?.abort(), [])

  async function handleSubmit(event) {
    event.preventDefault()
    if (submissionLocked.current || disabled) return

    const trimmedName = name.trim()
    if (!trimmedName || trimmedName.length > 100) {
      setError('Enter a floor name between 1 and 100 characters.')
      return
    }

    submissionLocked.current = true
    setIsSubmitting(true)
    setError(null)
    const controller = new AbortController()
    activeController.current = controller

    try {
      const floor = await createProjectFloor(
        projectId,
        { name: trimmedName },
        { signal: controller.signal },
      )
      setName('')
      onCreated(floor)
    } catch (requestError) {
      if (requestError.name !== 'AbortError') {
        setError(getCreationError(requestError))
      }
    } finally {
      submissionLocked.current = false
      setIsSubmitting(false)
      activeController.current = null
    }
  }

  const controlsDisabled = disabled || isSubmitting

  return (
    <form className="project-floor-create-form" onSubmit={handleSubmit}>
      <label htmlFor="project-floor-name">
        Floor name
        <input
          id="project-floor-name"
          type="text"
          value={name}
          required
          maxLength={100}
          disabled={controlsDisabled}
          placeholder="Ground Floor"
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      {error && <div className="project-alert project-alert-error" role="alert">{error}</div>}
      <button className="btn btn-outline-dark" type="submit" disabled={controlsDisabled}>
        {isSubmitting ? 'Creating floor…' : 'Create floor'}
      </button>
    </form>
  )
}
