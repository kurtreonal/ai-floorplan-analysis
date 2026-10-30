import { useEffect, useState } from 'react'

import {
  listProjectFloors,
  ProjectFloorApiError,
} from '../../api/projectFloors.js'
import { FloorPlanApiError, listFloorPlans,originalFloorPlanHref } from '../../api/floorPlans.js'
import {
  listProcessingJobs,
  ProcessingJobApiError,
} from '../../api/processingJobs.js'
import { CreateProjectFloorForm } from './CreateProjectFloorForm.jsx'
import { FloorPlanUploadForm } from './FloorPlanUploadForm.jsx'
import { ProcessingJobPanel } from './ProcessingJobPanel.jsx'
import { orderFloors, orderNamed } from '../../utils/listOrder.js'
import { FloorPlanLifecycleControls, FloorPlanTrash } from './FloorPlanLifecycleControls.jsx'
import {PlanNameEditor} from './PlanNameEditor.jsx'
import {PlanLayoutSettings} from './PlanLayoutSettings.jsx'


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

function getPlanListError(error) {
  if (error instanceof FloorPlanApiError || error instanceof ProcessingJobApiError) {
    if (error.status === 401) {
      window.location.replace('#/signin?reason=session-expired')
      return null
    }
    if (error.status === 403) return 'You are not authorized to view these floor plans.'
    if (error.status === 404) return 'The selected project or floor plan is no longer available.'
  }
  return 'Persisted floor plans are temporarily unavailable.'
}

export function ProjectFloorUploadPanel({ projectId, session }) {
  const [floors, setFloors] = useState([])
  const [selectedFloorId, setSelectedFloorId] = useState('')
  const [loadState, setLoadState] = useState('loading')
  const [error, setError] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [isUploading, setIsUploading] = useState(false)
  const [sessionUploads, setSessionUploads] = useState([])
  const [persistedPlans, setPersistedPlans] = useState([])
  const [persistedPlanScope, setPersistedPlanScope] = useState(null)
  const [planLoadState, setPlanLoadState] = useState('idle')
  const [planError, setPlanError] = useState(null)
  const [planRefreshKey, setPlanRefreshKey] = useState(0)
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

  useEffect(() => {
    if (loadState !== 'ready' || !selectedFloorId) {
      return undefined
    }

    const controller = new AbortController()
    let current = true

    async function loadPlans() {
      setPlanLoadState('loading')
      setPlanError(null)
      try {
        const plans = await listFloorPlans(projectId, {
          projectFloorId: selectedFloorId,
          signal: controller.signal,
        })
        const histories = await Promise.all(
          plans.map((plan) => listProcessingJobs(plan.id, { signal: controller.signal })),
        )
        if (!current) return
        const records = plans.map((plan, index) => ({
          ...plan,
          history: histories[index],
          latest_job: histories[index][0] || null,
        }))
        setPersistedPlans(records)
        setPersistedPlanScope(`${projectId}:${selectedFloorId}`)
        setSessionUploads((uploads) => uploads.filter(
          (upload) => !records.some((record) => record.id === upload.id),
        ))
        setPlanLoadState('ready')
      } catch (requestError) {
        if (requestError.name !== 'AbortError' && current) {
          setPlanError(getPlanListError(requestError))
          setPlanLoadState('error')
        }
      }
    }

    loadPlans()
    return () => {
      current = false
      controller.abort()
    }
  }, [loadState, planRefreshKey, projectId, selectedFloorId])

  function handleFloorCreated(floor) {
    setFloors((currentFloors) => [...currentFloors, floor])
    setSelectedFloorId(floor.id)
  }

  function handleUploaded(floorPlan) {
    const selectedFloor = floors.find(
      (floor) => String(floor.id) === String(selectedFloorId),
    )
    setSessionUploads((uploads) => [
      ...uploads.filter((upload) => upload.id !== floorPlan.id),
      {
        ...floorPlan,
        floor_name: selectedFloor?.name || 'Unknown floor',
        history: [],
        latest_job: floorPlan.initial_job ? { ...floorPlan.initial_job, type: 'floor_plan_analysis', progress: 0, error_message: null } : null,
      },
    ])
    setPlanRefreshKey((key) => key + 1)
  }

  function handlePlanChanged(planId) {
    setSessionUploads(uploads => uploads.filter(plan => plan.id !== planId))
    setPersistedPlans(plans => plans.filter(plan => plan.id !== planId))
    setPlanRefreshKey(key => key + 1)
  }

  // A floor switch renders before its effect starts. Never relabel old cards
  // or build new-floor editor links from the previous request's records.
  const currentPersistedPlans = persistedPlanScope === `${projectId}:${selectedFloorId}`
    ? persistedPlans.filter((plan) => String(plan.project_floor_id) === String(selectedFloorId))
    : []
  const visiblePlans = [
    ...currentPersistedPlans,
    ...sessionUploads.filter(
      (upload) => String(upload.project_floor_id) === String(selectedFloorId)
        && !currentPersistedPlans.some((plan) => plan.id === upload.id),
    ),
  ]
  const selectedFloorName = floors.find(
    (floor) => String(floor.id) === String(selectedFloorId),
  )?.name || 'Unknown floor'

  return (
    <section className="project-floor-panel" aria-labelledby="project-floor-panel-title">
      <div className="project-section-heading">
        <span className="project-kicker mono">FLOOR PLANS</span>
        <h2 id="project-floor-panel-title">Project floor plans</h2>
        <p>Add floors, choose a floor below, then upload its plans. Plan names stay Pending until the designer names them.</p>
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
              {floors.length > 0 && <label>Floor
                <select value={selectedFloorId} onChange={(event) => setSelectedFloorId(event.target.value)}>
                  {orderFloors(floors).map((floor) => <option key={floor.id} value={floor.id}>{floor.name}</option>)}
                </select>
              </label>}
            </div>
          )}

          {isDesigner && (
            <div className="project-floor-designer-tools">
              <section className="project-floor-create-block"><h3>Add floors</h3>
                <CreateProjectFloorForm
                  projectId={projectId}
                  existingCount={floors.length}
                  disabled={isUploading}
                  onCreated={handleFloorCreated}
                />
              </section>

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
                      {orderFloors(floors).map((floor) => (
                        <option key={floor.id} value={floor.id}>{floor.name}</option>
                      ))}
                    </select>
                  </label>
                  <PlanNameEditor key={`floor-${selectedFloorId}-${selectedFloorName}`} floor projectId={projectId} item={{id:Number(selectedFloorId),name:selectedFloorName}} onSaved={name=>setFloors(current=>current.map(f=>String(f.id)===String(selectedFloorId)?{...f,name}:f))}/>
                  <div className="studio-table-scroll"><table className="studio-floorplan-table plan-upload-table"><thead><tr><th>Plan name</th><th>Add floor-plan file</th></tr></thead><tbody><tr><td><span className="project-status">Pending designer name</span></td><td>
                  <FloorPlanUploadForm
                    key={selectedFloorId}
                    projectId={projectId}
                    projectFloorId={selectedFloorId}
                    onUploaded={handleUploaded}
                    onUploadingChange={setIsUploading}
                    onUnavailable={() => setRefreshKey((key) => key + 1)}
                  />
                  </td></tr></tbody></table></div>
                </div>
              )}
            </div>
          )}

          {floors.length > 0 && planLoadState === 'loading' && (
            <div className="project-floor-state" role="status">
              <span className="auth-spinner" aria-hidden="true" />
              Loading persisted floor plans...
            </div>
          )}


          {planLoadState === 'error' && (
            <div className="project-floor-state project-state-error">
              <p role="alert">{planError}</p>
              <button
                className="btn btn-outline-dark"
                type="button"
                onClick={() => setPlanRefreshKey((key) => key + 1)}
              >
                Retry floor plans
              </button>
            </div>
          )}

          {planLoadState === 'ready' && visiblePlans.length === 0 && (
            <div className="project-floor-empty">
              <h3>No floor plans on this floor.</h3>
              <p>Upload an original plan to begin analysis.</p>
            </div>
          )}

          {visiblePlans.length > 0 && (
            <section className="session-upload-section" aria-labelledby="persisted-plan-title">
              <h3 id="persisted-plan-title">Saved floor plans</h3>
              <div className="studio-table-scroll">
              <table className="studio-floorplan-table">
                <caption className="sr-only">Saved floor plans for {selectedFloorName}</caption>
                <thead><tr><th scope="col">Plan name / file</th><th scope="col" className="plan-status-cell">Status</th><th scope="col" className="plan-actions-cell">Actions</th></tr></thead>
                <tbody>
                {orderNamed(visiblePlans, plan => plan.display_name || plan.original_filename).map((upload) => (
                  <tr key={upload.id}>
                    <th scope="row"><span className="plan-filename">{upload.display_name || 'Pending'}</span><small className="account-secondary" title={upload.original_filename}>{upload.original_filename}</small></th>
                    <ProcessingJobPanel
                      key={`${upload.id}-${upload.latest_job?.job_id || 'none'}-${upload.latest_job?.updated_at || 'none'}`}
                      compact
                      projectId={projectId}
                      projectFloorId={Number(selectedFloorId)}
                      floorPlanId={upload.id}
                      originalFilename={upload.original_filename}
                      optionsContent={<PlanLayoutSettings projectId={projectId} planId={upload.id} canEdit={isDesigner} onSaved={()=>setPlanRefreshKey(key=>key+1)}/>}
                      initialJob={upload.latest_job}
                      canStart={isDesigner}
                    >
                    <div className="plan-file-options"><a className="project-open-link" href={originalFloorPlanHref(projectId,upload.id)} target="_blank" rel="noopener noreferrer">Download original</a>{isDesigner && <PlanNameEditor key={`${upload.id}-${upload.display_name || ''}`} projectId={projectId} item={upload} onSaved={()=>setPlanRefreshKey(key=>key+1)}/>}</div>
                    <dl className="plan-file-details">
                      <div><dt>Floor</dt><dd>{upload.floor_name || selectedFloorName}</dd></div>
                      <div><dt>Upload status</dt><dd>{upload.processing_status}</dd></div>
                      <div><dt>MIME type</dt><dd>{upload.mime_type}</dd></div>
                      <div><dt>File size</dt><dd>{upload.file_size.toLocaleString()} bytes</dd></div>
                      <div><dt>Floor-plan ID</dt><dd>{upload.id}</dd></div>
                      <div><dt>Job history</dt><dd>{upload.history.length}</dd></div>
                    </dl>
                    {isDesigner && <FloorPlanLifecycleControls projectId={projectId} planId={upload.id} onChanged={handlePlanChanged} />}
                    </ProcessingJobPanel>
                  </tr>
                ))}
                </tbody>
              </table>
              </div>
            </section>
          )}
          <FloorPlanTrash key={projectId} projectId={projectId} refreshKey={planRefreshKey} onChanged={handlePlanChanged} canEdit={isDesigner} />
        </>
      )}
    </section>
  )
}
