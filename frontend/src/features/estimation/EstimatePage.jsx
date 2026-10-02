import { useEffect, useRef, useState } from 'react'
import { Calculator, Layers3, Receipt, ShieldCheck } from 'lucide-react'
import { createEstimate, EstimateApiError, fetchEstimateOptions, listEstimates } from '../../api/estimates.js'
import { getProjectHref } from '../../routes/projectRoutes.js'
import { Button } from '../../components/ui/button.jsx'
import { Input } from '../../components/ui/input.jsx'

function money(value, currency) {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(Number(value))
}

function failure(error) {
  if (error instanceof EstimateApiError) {
    if (error.status === 401) { window.location.replace('#/signin?reason=session-expired'); return 'Your session has expired.' }
    if (error.status === 403) return 'Your account cannot perform this estimate operation.'
    if (error.status === 404) return 'This project or estimate is unavailable.'
    if (error.code === 'STALE_ROUTE') return 'The route changed. Reload the estimate inputs before generating a snapshot.'
    if (error.status === 422) return 'Review all material mappings, current prices and route inputs. The server did not accept this estimate.'
  }
  return 'The estimate service is unavailable. Saved prices have not been changed.'
}

function MaterialSelect({ label, materials, value, onChange, required = true }) {
  return <label className="studio-field"><span>{label}</span><select required={required} value={value} onChange={(event) => onChange(event.target.value)}><option value="">Choose priced material…</option>{materials.map((material) => <option key={material.id} value={material.id}>{material.code} · {material.name} ({material.unit})</option>)}</select></label>
}

export function EstimatePage({ projectId, session }) {
  const [records, setRecords] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [historyState, setHistoryState] = useState('loading')
  const [options, setOptions] = useState(null)
  const [optionsError, setOptionsError] = useState(null)
  const [historyError, setHistoryError] = useState(null)
  const [attempt, setAttempt] = useState(0)
  const [bindings, setBindings] = useState({})
  const [conduit, setConduit] = useState('')
  const [wire, setWire] = useState('')
  const [conductors, setConductors] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [saveState, setSaveState] = useState('idle')
  const [saveError, setSaveError] = useState(null)
  const retryPayload = useRef(null)
  const inFlight = useRef(false)
  const saveController = useRef(null)
  const selected = records.find((record) => record.id === selectedId) || records[0]
  const designer = session?.user?.role === 'DESIGNER'
  const pricedMaterials = options?.materials.filter((material) => material.has_price) || []
  const lengthMaterials = pricedMaterials.filter((material) => material.unit === 'meter')

  useEffect(() => {
    const controller = new AbortController()
    listEstimates(projectId, { signal: controller.signal }).then((items) => {
      if (controller.signal.aborted) return
      setRecords([...items].sort((a, b) => b.version_number - a.version_number)); setHistoryState('ready')
    }).catch((error) => { if (!controller.signal.aborted) { setHistoryError(failure(error)); setHistoryState('error') } })
    fetchEstimateOptions(projectId, { signal: controller.signal }).then((value) => {
      if (controller.signal.aborted) return
      setOptions(value); setBindings({}); setConduit(''); setWire(''); setConductors(''); setConfirmed(false)
    }).catch((error) => { if (!controller.signal.aborted) setOptionsError(failure(error)) })
    return () => controller.abort()
  }, [projectId, attempt])
  useEffect(() => () => saveController.current?.abort(), [])

  function reloadInputs() {
    setHistoryState('loading'); setOptions(null); setOptionsError(null); setHistoryError(null)
    setAttempt((value) => value + 1)
  }

  async function generate(event) {
    event.preventDefault()
    if (!designer || inFlight.current || !options?.route_version_id || options.stale) return
    const payload = retryPayload.current || {
      request_id: globalThis.crypto.randomUUID(), route_version_id: options.route_version_id,
      components: options.components.map((component) => ({ class_id: component.class_id,
        material_id: Number(bindings[component.class_id]?.material), units_per_symbol: bindings[component.class_id]?.units })),
      conduit_material_id: Number(conduit), wire_material_id: Number(wire), conductor_count: Number(conductors), mappings_confirmed: confirmed,
    }
    retryPayload.current = payload
    inFlight.current = true
    const controller = new AbortController(); saveController.current = controller
    setSaveState('saving'); setSaveError(null)
    try {
      const record = await createEstimate(projectId, payload, { signal: controller.signal })
      if (controller.signal.aborted) return
      setRecords((current) => [record, ...current.filter((item) => item.id !== record.id)])
      setSelectedId(record.id); retryPayload.current = null; setSaveState('idle'); setConfirmed(false)
    } catch (error) {
      if (controller.signal.aborted) return
      const uncertain = !error.status || error.status >= 500
      setSaveState(uncertain ? 'uncertain' : 'idle')
      setSaveError(uncertain ? 'The save result is uncertain. Retry the identical request to retrieve or create the same snapshot; inputs are locked to prevent duplication.' : failure(error))
      if (!uncertain) retryPayload.current = null
    } finally { inFlight.current = false }
  }

  return <article className="studio-estimate-page" aria-labelledby="estimate-title">
    <a className="project-back-link" href={getProjectHref(projectId)}>← Back to project</a>
    <header className="studio-page-heading"><div><span className="project-kicker mono">MATERIAL TAKEOFF / SAVED SNAPSHOTS</span><h1 id="estimate-title">Cost estimation</h1><p>Reviewed quantities, saved routes and database prices. No invented allowances or live repricing.</p></div><Button variant="outline" disabled={saveState !== 'idle'} onClick={reloadInputs}>Reload inputs</Button></header>
    <div className="studio-metric-grid">
      <section><Receipt aria-hidden="true" /><span>Selected snapshot</span><strong>{selected ? money(selected.total, selected.currency) : '—'}</strong><small>Backend captured total · {selected ? `version ${selected.version_number}` : 'no saved estimate'}</small></section>
      <section><Layers3 aria-hidden="true" /><span>Saved estimates</span><strong>{historyState === 'ready' ? records.length : '—'}</strong><small>Historical unit prices remain fixed</small></section>
      <section><ShieldCheck aria-hidden="true" /><span>Route readiness</span><strong>{options ? options.route_version_id && !options.stale ? 'Current' : 'Needs review' : 'Unavailable'}</strong><small>{options?.route_version_id ? `Route version ID ${options.route_version_id}` : 'Save a measured route first'}</small></section>
    </div>
    <div className="studio-estimate-workbench">
      <section className="studio-panel" aria-labelledby="estimate-history-title"><div className="studio-panel-heading"><h2 id="estimate-history-title">Estimate breakdown</h2><span className="mono">CAPTURED PRICES</span></div>
        {historyState === 'loading' && <p role="status">Loading saved estimates…</p>}
        {historyError && <p role="alert">{historyError}</p>}
        {historyState === 'ready' && !records.length && <div className="project-empty-state"><Calculator size={28} aria-hidden="true" /><h3>No saved estimates yet.</h3><p>Save reviewed geometry and a measured route, then map materials to create a price snapshot.</p></div>}
        {selected && <><label className="studio-field"><span>Estimate version</span><select value={selected.id} onChange={(event) => setSelectedId(Number(event.target.value))}>{records.map((record) => <option key={record.id} value={record.id}>Version {record.version_number} · {money(record.total, record.currency)}</option>)}</select></label><div className="studio-table-scroll"><table className="studio-estimate-table"><thead><tr><th>Material</th><th>Quantity</th><th>Unit price</th><th>Line total</th></tr></thead><tbody>{selected.items.map((item) => <tr key={item.line_number}><td><strong>{item.material_name}</strong><small>{item.material_code}</small></td><td>{item.quantity} {item.unit}</td><td>{money(item.captured_unit_price, selected.currency)}</td><td>{money(item.line_total, selected.currency)}</td></tr>)}</tbody><tfoot><tr><th colSpan="3">Captured total</th><td>{money(selected.total, selected.currency)}</td></tr></tfoot></table></div><p className="studio-panel-note">Snapshot #{selected.id}. Later material-price updates do not alter these captured amounts. Planning estimate, not professional approval.</p></>}
      </section>
      <aside className="studio-panel" aria-labelledby="estimate-inputs-title"><div className="studio-panel-heading"><h2 id="estimate-inputs-title">Generate snapshot</h2><span className="mono">EXPLICIT MAPPINGS</span></div>
        {!designer && <p role="note">Admin read-only view. A Designer generates estimates.</p>}
        {optionsError && <p role="alert">{optionsError}</p>}
        {options && (!options.route_version_id || options.stale) && <p role="note">Save a current route against reviewed layouts before generating an estimate. Existing snapshots remain available.</p>}
        {designer && options?.route_version_id && !options.stale && <form onSubmit={generate}>
          <fieldset disabled={saveState !== 'idle'}><legend className="sr-only">Material and route mappings</legend>
            <p className="studio-panel-note">Route #{options.route_version_id} · {options.floors.length} floors. Specify conversion factors; none are assumed.</p>
            {options.components.map((component) => <div className="studio-material-binding" key={component.class_id}><p><strong>{component.class_name}</strong><small>{component.quantity} reviewed symbols · class {component.class_id}</small></p><MaterialSelect label={`Material for ${component.class_name}`} materials={pricedMaterials} value={bindings[component.class_id]?.material || ''} onChange={(material) => setBindings((current) => ({ ...current, [component.class_id]: { ...current[component.class_id], material } }))} /><label className="studio-field"><span>Material units per {component.class_name}</span><Input type="number" min="0.0001" max="1000" step="0.0001" required value={bindings[component.class_id]?.units || ''} onChange={(event) => setBindings((current) => ({ ...current, [component.class_id]: { ...current[component.class_id], units: event.target.value } }))} /></label></div>)}
            <MaterialSelect label="Conduit material (meter)" materials={lengthMaterials} value={conduit} onChange={setConduit} /><MaterialSelect label="Wire material (meter)" materials={lengthMaterials} value={wire} onChange={setWire} />
            <label className="studio-field"><span>Conductor count</span><Input type="number" min="1" max="1000" step="1" required value={conductors} onChange={(event) => setConductors(event.target.value)} /></label>
            <label className="studio-confirmation"><input type="checkbox" required checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />I reviewed these material mappings and conversion factors.</label>
          </fieldset>
          <Button type="submit" disabled={saveState === 'saving'}>{saveState === 'saving' ? 'Saving snapshot…' : saveState === 'uncertain' ? 'Retry identical snapshot request' : 'Generate estimate snapshot'}</Button>
        </form>}
        {saveError && <p role="alert">{saveError}</p>}
      </aside>
    </div>
  </article>
}
