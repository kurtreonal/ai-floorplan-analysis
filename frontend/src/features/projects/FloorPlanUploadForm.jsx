import { useEffect, useRef, useState } from 'react'

import { FloorPlanApiError, uploadFloorPlan } from '../../api/floorPlans.js'


export const FLOOR_PLAN_ACCEPT = '.jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf'

const MIME_BY_EXTENSION = {
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.png': 'image/png',
  '.pdf': 'application/pdf',
}

function validateSelectedFile(file) {
  const dotIndex = file.name.lastIndexOf('.')
  const extension = dotIndex >= 0 ? file.name.slice(dotIndex).toLowerCase() : ''
  const expectedMime = MIME_BY_EXTENSION[extension]

  if (!expectedMime) {
    return 'Choose a JPEG, PNG, or PDF floor plan.'
  }
  if (!file.type || file.type.toLowerCase() !== expectedMime) {
    return 'The selected file type does not match its filename extension.'
  }
  return null
}

function getUploadError(error) {
  if (error instanceof FloorPlanApiError) {
    if (error.status === 401) {
      window.location.replace('#/signin?reason=session-expired')
      return null
    }
    if (error.status === 413) {
      return 'The selected file exceeds the configured upload-size limit.'
    }
    if (error.status === 415 || error.status === 422) return error.message
    if (error.status === 403) return 'You are not authorized to upload floor plans.'
    if (error.status === 404) return 'The selected project or floor is no longer available.'
    if (error.status === 503 || error.status === 0) {
      return 'The floor-plan upload service is temporarily unavailable.'
    }
  }
  return 'The floor-plan upload could not be completed. Please try again.'
}

export function FloorPlanUploadForm({
  projectId,
  projectFloorId,
  onUploaded,
  onUploadingChange = () => {},
  onUnavailable = () => {},
}) {
  const [file, setFile] = useState(null)
  const [error, setError] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const uploadLocked = useRef(false)
  const fileInput = useRef(null)
  const activeController = useRef(null)

  useEffect(() => () => activeController.current?.abort(), [])

  function handleFileChange(event) {
    const selectedFile = event.target.files?.[0] || null
    setError(null)
    if (!selectedFile) {
      setFile(null)
      return
    }

    const validationError = validateSelectedFile(selectedFile)
    if (validationError) {
      setFile(null)
      setError(validationError)
      event.target.value = ''
      return
    }
    setFile(selectedFile)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (uploadLocked.current) return
    if (!projectFloorId) {
      setError('Select a project floor before uploading.')
      return
    }
    if (!file) {
      setError('Choose a JPEG, PNG, or PDF floor plan.')
      return
    }

    const validationError = validateSelectedFile(file)
    if (validationError) {
      setError(validationError)
      return
    }

    uploadLocked.current = true
    setIsUploading(true)
    onUploadingChange(true)
    setError(null)
    const controller = new AbortController()
    activeController.current = controller

    try {
      const uploadedFloorPlan = await uploadFloorPlan(
        projectId,
        { projectFloorId, file },
        { signal: controller.signal },
      )
      onUploaded(uploadedFloorPlan)
      setFile(null)
      if (fileInput.current) fileInput.current.value = ''
    } catch (requestError) {
      if (requestError.name !== 'AbortError') {
        setError(getUploadError(requestError))
        if (requestError instanceof FloorPlanApiError && requestError.status === 404) {
          onUnavailable()
        }
      }
    } finally {
      uploadLocked.current = false
      setIsUploading(false)
      onUploadingChange(false)
      activeController.current = null
    }
  }

  return (
    <form className="floor-plan-upload-form" onSubmit={handleSubmit}>
      <label htmlFor="floor-plan-file">
        Floor-plan file
        <input
          ref={fileInput}
          id="floor-plan-file"
          type="file"
          accept={FLOOR_PLAN_ACCEPT}
          disabled={isUploading}
          onChange={handleFileChange}
        />
      </label>
      <p className="floor-plan-form-help">Supported formats: JPEG, PNG, and PDF.</p>
      {file && (
        <p className="floor-plan-selected-file">
          Selected: <strong>{file.name}</strong> ({file.size.toLocaleString()} bytes)
        </p>
      )}
      {isUploading && (
        <div className="floor-plan-uploading" role="status" aria-live="polite">
          <span className="auth-spinner" aria-hidden="true" />
          Uploading floor plan…
        </div>
      )}
      {error && <div className="project-alert project-alert-error" role="alert">{error}</div>}
      <button className="btn btn-accent" type="submit" disabled={isUploading}>
        {isUploading ? 'Uploading…' : 'Upload floor plan'}
      </button>
    </form>
  )
}
