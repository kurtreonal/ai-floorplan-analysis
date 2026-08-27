import { useEffect, useState } from 'react'

import {
  listProjectFloors,
  ProjectFloorApiError,
} from '../../api/projectFloors.js'
import { CreateProjectFloorForm } from './CreateProjectFloorForm.jsx'
import { FloorPlanUploadForm } from './FloorPlanUploadForm.jsx'
import { ProcessingJobPanel } from './ProcessingJobPanel.jsx'


function getFloorListError(error) {
  if (error instanceof ProjectFloorApiError) {
    if (error.status === 401) {
      window.location.replace('#/signin?reason=session-expired')
      return null
    }
    if (error.status === 403) return 'You are not authorized to view project floors.'
    if (error.status === 404) return 'The selected project is no longer available.'
    if (error.status === 503 || error.status === 0) {
      return 'Project floors are temporarily unavailable.'
    }
  }
  return 'Project floors could not be loaded. Please try again.'
}

export function ProjectFloorUploadPanel({ projectId, session }) {
  const [floors, setFloors] = useState([])
  const [selectedFloorId, setSelectedFloorId] = useState('')
  const [loadState, setLoadState] = useState('loading')
  const [error, setError] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [isUploading, setIsUploading] = useState(false)
  const [sessionUploads, setSessionUploads] = useState([])
  const role = session?.user?.role
  const isDesigner = role === 'DESIGNER'

  useEffect(() => {
    const controller = new AbortController()

    async function loadFloors() {
      setLoadState('loading')
      setError(null)
      try {
        const floorData = await listProjectFloors(projectId, {
          signal: controller.signal,
        })
        setFloors(floorData)
        setSelectedFloorId((currentId) => {
          if (floorData.some((floor) => String(floor.id) === String(currentId))) {
            return currentId
          }
          return floorData[0]?.id || ''
        })
        setLoadState('ready')
      } catch (requestError) {
        if (requestError.name !== 'AbortError') {
          setError(getFloorListError(requestError))
          setLoadState('error')
        }
      }
    }

    loadFloors()
    return () => controller.abort()
  }, [projectId, refreshKey])

  function handleFloorCreated(floor) {
    setFloors((currentFloors) => [...currentFloors, floor])
    setSelectedFloorId(floor.id)
  }

  function handleUploaded(floorPlan) {
    const selectedFloor = floors.find(
      (floor) => String(floor.id) === String(selectedFloorId),
    )
    setSessionUploads((uploads) => [
      ...uploads,
      { ...floorPlan, floor_name: selectedFloor?.name || 'Unknown floor' },
    ])
  }

  return (
    <section className="project-floor-panel" aria-labelledby="project-floor-panel-title">
      <div className="project-section-heading">
        <span className="project-kicker mono">FLOOR PLANS</span>
        <h2 id="project-floor-panel-title">Project floor plans</h2>
        <p>Select a project floor, then upload its original JPEG, PNG, or PDF plan.</p>
      </div>

      {loadState === 'loading' && (
        <div className="project-floor-state" role="status">
          <span className="auth-spinner" aria-hidden="true" />
          Loading project floors…
        </div>
      )}

      {loadState === 'error' && (
        <div className="project-floor-state project-state-error">
          <p role="alert">{error}</p>
          <button
            className="btn btn-outline-dark"
            type="button"
            onClick={() => setRefreshKey((key) => key + 1)}
          >
            Retry
          </button>
        </div>
      )}

      {loadState === 'ready' && (
        <>
          {floors.length === 0 && (
            <div className="project-floor-empty">
              <h3>No project floors yet.</h3>
              <p>Create the first floor before uploading a floor plan.</p>
            </div>
          )}

          {role === 'ADMIN' && (
            <div className="project-floor-admin" role="note">
              <p>Floor-plan uploads require a Designer account.</p>
              {floors.length > 0 && (
                <ul>
                  {floors.map((floor) => (
                    <li key={floor.id}>
                      <strong>{floor.name}</strong>
                      <span className="mono">FLOOR #{floor.id} · ORDER {floor.sort_order}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {isDesigner && (
            <div className="project-floor-designer-tools">
              <div className="project-floor-create-block">
                <h3>Create a project floor</h3>
                <CreateProjectFloorForm
                  projectId={projectId}
                  disabled={isUploading}
                  onCreated={handleFloorCreated}
                />
              </div>

              {floors.length > 0 && (
                <div className="project-floor-upload-block">
                  <label className="project-floor-selector" htmlFor="project-floor-selector">
                    Project floor
                    <select
                      id="project-floor-selector"
                      value={selectedFloorId}
                      disabled={isUploading}
                      onChange={(event) => setSelectedFloorId(event.target.value)}
                    >
                      {floors.map((floor) => (
                        <option key={floor.id} value={floor.id}>{floor.name}</option>
                      ))}
                    </select>
                  </label>
                  <FloorPlanUploadForm
                    projectId={projectId}
                    projectFloorId={selectedFloorId}
                    onUploaded={handleUploaded}
                    onUploadingChange={setIsUploading}
                    onUnavailable={() => setRefreshKey((key) => key + 1)}
                  />
                </div>
              )}
            </div>
          )}

          {sessionUploads.length > 0 && (
            <section className="session-upload-section" aria-labelledby="session-upload-title">
              <h3 id="session-upload-title">Uploaded this session</h3>
              <div className="session-upload-grid">
                {sessionUploads.map((upload) => (
                  <article className="session-upload-card" key={upload.id}>
                    <strong>{upload.original_filename}</strong>
                    <dl>
                      <div><dt>Floor</dt><dd>{upload.floor_name}</dd></div>
                      <div><dt>MIME type</dt><dd>{upload.mime_type}</dd></div>
                      <div><dt>File size</dt><dd>{upload.file_size.toLocaleString()} bytes</dd></div>
                      <div><dt>Status</dt><dd>{upload.processing_status}</dd></div>
                      <div><dt>Floor-plan ID</dt><dd>{upload.id}</dd></div>
                    </dl>
                    {isDesigner && (
                      <ProcessingJobPanel
                        floorPlanId={upload.id}
                        originalFilename={upload.original_filename}
                      />
                    )}
                  </article>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </section>
  )
}
