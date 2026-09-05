import { useEffect, useRef, useState } from 'react'

import { fetchAnalysisSettings, saveFloorElevation, savePageScale } from '../../api/analysisSettings.js'

function errorMessage(error) {
  if (error.status === 401) return 'Your session expired. Sign in again to manage analysis settings.'
  if (error.status === 403) return 'You are not authorized to change these settings.'
  if (error.status === 404) return 'The selected floor or page is no longer available.'
  if (error.status === 422) return 'Check the numeric bounds and provide evidence notes.'
  return 'Analysis settings are unavailable. Please retry.'
}

function ApprovalForm({ record, scale = false, canEdit, onSave }) {
  const [value, setValue] = useState(String((scale ? record.pixels_per_meter : record.elevation_meters) ?? ''))
  const [width, setWidth] = useState(String(record.reference_width_pixels ?? ''))
  const [height, setHeight] = useState(String(record.reference_height_pixels ?? ''))
  const [notes, setNotes] = useState(record.evidence_notes ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const request = useRef(null)
  useEffect(() => () => request.current?.abort(), [])

  async function submit(event) {
    event.preventDefault()
    if (!canEdit || saving) return
    const controller = new AbortController()
    request.current = controller
    setSaving(true)
    setError(null)
    const number = value.trim() === '' ? null : Number(value)
    const body = scale ? {
      pixels_per_meter: number,
      reference_width_pixels: number === null ? null : Number(width),
      reference_height_pixels: number === null ? null : Number(height),
      evidence_notes: notes.trim(),
    } : { elevation_meters: number, evidence_notes: notes.trim() }
    try {
      await onSave(body, { signal: controller.signal })
    } catch (failure) {
      if (!controller.signal.aborted) setError(errorMessage(failure))
    } finally {
      if (!controller.signal.aborted) setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="analysis-approval-form">
      <p>{record.state === 'approved' ? 'Designer-approved' : 'Unresolved — requires Designer review'}</p>
      {record.reviewed_by_user_id && <p>Reviewed by user #{record.reviewed_by_user_id} on {record.created_at}</p>}
      <fieldset disabled={!canEdit || saving}>
        <label>
          {scale ? 'Scale (pixels per meter)' : 'Floor elevation (meters from project datum)'}
          <input type="number" step="any" min={scale ? 0.000001 : -10000} max={scale ? 1000000 : 10000}
            value={value} onChange={(event) => setValue(event.target.value)} />
        </label>
        {scale && <>
          <label>Reference image width (pixels)
            <input type="number" min="1" max="100000" step="1" required={value !== ''}
              value={width} onChange={(event) => setWidth(event.target.value)} />
          </label>
          <label>Reference image height (pixels)
            <input type="number" min="1" max="100000" step="1" required={value !== ''}
              value={height} onChange={(event) => setHeight(event.target.value)} />
          </label>
        </>}
        <label>Evidence notes
          <textarea required maxLength="1000" value={notes} onChange={(event) => setNotes(event.target.value)} />
        </label>
        {canEdit && <button className="btn btn-outline-dark" type="submit">{saving ? 'Saving...' : 'Save reviewed settings'}</button>}
      </fieldset>
      {canEdit && <p>Leave the value blank to mark it unresolved. Describe the measurement reference or reason in the notes.</p>}
      {error && <p role="alert">{error}</p>}
    </form>
  )
}

export function AnalysisSettingsPanel({ projectId, floorId, canEdit }) {
  const [open, setOpen] = useState(false)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [refresh, setRefresh] = useState(0)
  useEffect(() => {
    if (!open) return undefined
    const controller = new AbortController()
    fetchAnalysisSettings(projectId, floorId, { signal: controller.signal }).then((settings) => {
      if (!controller.signal.aborted) setData(settings)
    }).catch((failure) => {
      if (!controller.signal.aborted) setError(errorMessage(failure))
    })
    return () => controller.abort()
  }, [open, projectId, floorId, refresh])

  return <section className="analysis-settings-panel" aria-label="Reviewed scale and elevation">
    <button type="button" className="btn btn-outline-dark" onClick={() => setOpen(!open)}>
      {open ? 'Hide scale and elevation' : 'Review scale and elevation'}
    </button>
    {open && <>
      <p>Scale and elevation must come from a reviewed measurement. Missing values do not block uploads.</p>
      {!data && !error && <p role="status">Loading analysis settings...</p>}
      {error && <><p role="alert">{error}</p><button type="button" onClick={() => { setError(null); setRefresh(refresh + 1) }}>Retry settings</button></>}
      {data && <>
        <h3>Floor elevation</h3>
        <ApprovalForm key={`elevation-${data.elevation.revision_id}`} record={data.elevation} canEdit={canEdit}
          onSave={async (body, options) => {
            const elevation = await saveFloorElevation(projectId, floorId, body, options)
            if (!options.signal.aborted) setData((current) => ({ ...current, elevation }))
          }} />
        {data.pages.length === 0 && <p>No source pages available. Upload a floor plan to review its scale.</p>}
        {data.pages.map((page) => <section key={page.floor_plan_page_id} aria-label={`Plan ${page.floor_plan_id}, page ${page.page_number}`}>
          <h3>Plan #{page.floor_plan_id}, page {page.page_number}</h3>
          <ApprovalForm key={`scale-${page.scale.revision_id}`} record={page.scale} scale canEdit={canEdit}
            onSave={async (body, options) => {
              const scale = await savePageScale(projectId, floorId, page.floor_plan_page_id, body, options)
              if (!options.signal.aborted) setData((current) => ({ ...current, pages: current.pages.map((item) => item.floor_plan_page_id === page.floor_plan_page_id ? { ...item, scale } : item) }))
            }} />
        </section>)}
      </>}
    </>}
  </section>
}
