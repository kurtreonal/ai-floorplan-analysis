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
    if (error.status === 422) return 'Check the floor name, floor count.'
    if (error.status === 503 || error.status === 0) {
      return 'The project-floor service is temporarily unavailable.'
    }
  }
  return 'The project floor could not be created. Please try again.'
}

export function CreateProjectFloorForm({ projectId, disabled = false, onCreated,existingCount=0 }) {
  const [name, setName] = useState('')
  const [count,setCount]=useState(1)
  const [error, setError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const submissionLocked = useRef(false)
  const activeController = useRef(null)

  useEffect(() => () => activeController.current?.abort(), [])

  async function handleSubmit(event) {
    event.preventDefault()
    if (submissionLocked.current || disabled) return

    const trimmedName = name.trim()
    if (trimmedName.length > 100 || !Number.isInteger(Number(count)) || count<1 || count>30) {
      setError('Use a floor name of at most 100 characters and add between 1 and 30 floors.')
      return
    }

    submissionLocked.current = true
    setIsSubmitting(true)
    setError(null)
    const controller = new AbortController()
    activeController.current = controller
    let created=0
    const total=Number(count)
    try {
      for(let index=0;index<Number(count);index++){
      const floor = await createProjectFloor(
        projectId,
        { name: trimmedName ? Number(count)>1?`${trimmedName} ${index+1}`:trimmedName:`Pending floor ${existingCount+index+1}` },
        { signal: controller.signal },
      )
      onCreated(floor)
      created++
      }
      setName('');setCount(1)
    } catch (requestError) {
      if (requestError.name !== 'AbortError') {
        if(created)setCount(total-created)
        setError(`${created?`${created} floors added. Retry the remaining ${total-created}. `:''}${getCreationError(requestError) || ''}`)
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
        Floor name <small>Optional · name later</small>
        <input
          id="project-floor-name"
          type="text"
          value={name}
          maxLength={100}
          disabled={controlsDisabled}
          placeholder="Pending until renamed"
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <label>Number of floors<input type="number" min="1" max="30" step="1" required value={count} disabled={controlsDisabled} onChange={event=>setCount(Number(event.target.value))}/></label>
      {error && <div className="project-alert project-alert-error" role="alert">{error}</div>}
      <button className="btn btn-outline-dark" type="submit" disabled={controlsDisabled}>
        {isSubmitting ? 'Adding floors…' : 'Add floors'}
      </button>
    </form>
  )
}
