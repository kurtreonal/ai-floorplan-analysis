import { useEffect, useRef, useState } from 'react'
import { applyProjectPrices, fetchProjectPrice, inspectProjectPrices, listProjectPrices, previewProjectPrices } from '../../api/projectPricing.js'
import { Button } from '../../components/ui/button.jsx'
import './clientPricing.css'

const emptyMapping = { kind: 'price_list', sheet: '', header_row: 1, columns: {}, currency: '' }
const fieldLabels = { name: 'Description', code: 'Code', specification: 'Specification', unit: 'Purchase unit', unit_price: 'Unit price', currency: 'Currency', quantity: 'Client quantity' }

export function ClientPricingPanel({ projectId, designer, disabled = false, estimateId, onVersionsChange, onApplied, defaultImportOpen = false }) {
  const [importOpen, setImportOpen] = useState(defaultImportOpen)
  const [file, setFile] = useState(null)
  const [mapping, setMapping] = useState(emptyMapping)
  const [inspection, setInspection] = useState(null)
  const [proposal, setProposal] = useState(null)
  const [choices, setChoices] = useState({})
  const [validated, setValidated] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [versions, setVersions] = useState([])
  const [selectedVersion, setSelectedVersion] = useState('')
  const [detailResult, setDetailResult] = useState(null)
  const [refresh, setRefresh] = useState(0)
  const controller = useRef(null)
  const retry = useRef(null)
  const [uncertain, setUncertain] = useState(false)
  const detail = detailResult?.version === selectedVersion && detailResult?.estimateId === estimateId ? detailResult.value : null

  useEffect(() => {
    const request = new AbortController()
    listProjectPrices(projectId, { signal: request.signal }).then(rows => {
      if (request.signal.aborted) return
      setVersions(rows)
      onVersionsChange?.(rows)
    }).catch(failure => { if (!request.signal.aborted) setError(failure.message) })
    return () => request.abort()
  }, [projectId, refresh, onVersionsChange])
  useEffect(() => {
    const request = new AbortController()
    if (selectedVersion) fetchProjectPrice(projectId, selectedVersion, { signal: request.signal, estimateId }).then(value => {
      if (!request.signal.aborted) setDetailResult({ version: selectedVersion, estimateId, value })
    }).catch(failure => { if (!request.signal.aborted) setError(failure.message) })
    return () => request.abort()
  }, [projectId, selectedVersion, estimateId])
  useEffect(() => () => controller.current?.abort(), [])

  const locked = busy || disabled || uncertain
  const headersCurrent = inspection && inspection.sheet === mapping.sheet && inspection.header_row === Number(mapping.header_row)
  const columnValues = Object.values(mapping.columns)
  const duplicateColumns = new Set(columnValues).size !== columnValues.length
  const canPreview = headersCurrent && mapping.columns.name && mapping.columns.unit && mapping.columns.unit_price
    && (mapping.columns.currency || /^[A-Z]{3}$/.test(mapping.currency))
    && (mapping.kind !== 'client_bom' || mapping.columns.quantity) && !duplicateColumns
  function invalidate() { setValidated(false); setConfirmed(false); setMessage('') }
  function updateMapping(patch) { setMapping(current => ({ ...current, ...patch })); setProposal(null); setChoices({}); invalidate() }
  function choose(rowId, patch) {
    setChoices(current => ({ ...current, [rowId]: { ...current[rowId], ...patch } }))
    invalidate()
  }
  async function run(action) {
    if (busy || disabled || (uncertain && action !== 'apply')) return
    const request = new AbortController(); controller.current = request
    setBusy(true); setError(''); setMessage('')
    try {
      if (action === 'inspect') {
        const value = await inspectProjectPrices(projectId, file, { signal: request.signal, sheet: mapping.sheet || undefined, headerRow: mapping.header_row })
        if (request.signal.aborted) return
        setInspection(value); setMapping(current => ({ ...current, sheet: value.sheet, columns: {} }))
        setProposal(null); setChoices({}); invalidate()
      } else {
        const selection = { mapping: { ...mapping, currency: mapping.currency || null }, choices: Object.entries(choices).map(([row_id, value]) => ({ row_id, ...value })) }
        if (action === 'preview') {
          const value = await previewProjectPrices(projectId, file, selection, { signal: request.signal })
          if (request.signal.aborted) return
          setProposal(value); setValidated(true); setConfirmed(false)
        } else {
          const payload = retry.current || { ...selection, request_id: crypto.randomUUID(), confirmed: true,
            file_sha256: proposal.file_sha256, preview_token: proposal.preview_token, expected_version: proposal.expected_version }
          retry.current = payload
          const value = await applyProjectPrices(projectId, file, payload, { signal: request.signal })
          if (request.signal.aborted) return
          retry.current = null; setUncertain(false); setProposal(null); setChoices({}); setConfirmed(false)
          setSelectedVersion(String(value.id)); setRefresh(current => current + 1)
          onApplied?.(value)
          setMessage('Client prices applied to this project. Saved estimates are unchanged.')
        }
      }
    } catch (failure) {
      if (!request.signal.aborted) {
        if (action === 'apply' && (!failure.status || failure.status >= 500)) {
          setUncertain(true); setError('Save result uncertain. Retry the identical import; inputs are locked to prevent duplication.')
        } else {
          setError(failure.message); retry.current = null; setUncertain(false)
          if (action === 'apply') { setValidated(false); setConfirmed(false) }
        }
      }
    } finally { if (!request.signal.aborted) setBusy(false) }
  }
  return <section className="studio-panel client-pricing" aria-labelledby="client-pricing-title">
    <div className="studio-panel-heading"><h2 id="client-pricing-title">Client BOM pricing</h2></div>
    <p>Upload the client’s materials and prices. Confirmed mappings automatically price matching draft items. Client quantities remain separate from calculated quantities.</p>
    {designer && <details open={importOpen} onToggle={event => setImportOpen(event.currentTarget.open)}><summary>Upload BOM pricing (XLSX or CSV)</summary>
      <fieldset disabled={locked}><legend className="sr-only">Client import</legend>
        <label>Client file<input type="file" accept=".xlsx,.csv" onChange={event => {
          setFile(event.target.files?.[0] || null); setMapping(emptyMapping); setInspection(null); setProposal(null); setChoices({}); invalidate(); setError('')
        }} /></label>
        <label>Import type<select value={mapping.kind} onChange={event => {
          const columns = { ...mapping.columns }; if (event.target.value === 'price_list') delete columns.quantity
          updateMapping({ kind: event.target.value, columns })
        }}><option value="price_list">Client price list</option><option value="client_bom">Client BOM with quantities</option></select></label>
        {inspection && <label>Worksheet<select value={mapping.sheet} onChange={event => updateMapping({ sheet: event.target.value })}>
          {inspection.sheets.map(sheet => <option key={sheet}>{sheet}</option>)}</select></label>}
        <label>Header row<input type="number" min="1" max="10000" value={mapping.header_row} onChange={event => updateMapping({ header_row: Number(event.target.value) })} /></label>
        <Button type="button" disabled={!file} onClick={() => run('inspect')}>Read headers</Button>
        {headersCurrent && <div className="client-column-map">
          {Object.entries(fieldLabels).filter(([key]) => key !== 'quantity' || mapping.kind === 'client_bom').map(([field, label]) => <label key={field}>{label} column
            <select value={mapping.columns[field] || ''} onChange={event => {
              const columns = { ...mapping.columns }; if (event.target.value) columns[field] = event.target.value; else delete columns[field]
              updateMapping({ columns })
            }}><option value="">Not mapped</option>{inspection.columns.map(column => <option key={column.id} value={column.id}>{column.id} · {column.label}</option>)}</select>
          </label>)}
          {!mapping.columns.currency && <label>Import currency<input maxLength="3" placeholder="e.g. PHP" value={mapping.currency} onChange={event => updateMapping({ currency: event.target.value.toUpperCase() })} /></label>}
        </div>}
        {duplicateColumns && <p role="alert">Map each field to a different source column.</p>}
        <Button type="button" disabled={!canPreview} onClick={() => run('preview')}>{proposal ? 'Validate mappings' : 'Preview rows'}</Button>
        {proposal && <><div className="client-price-table"><table><thead><tr><th>Source item</th><th>Quoted price</th><th>Material mapping</th><th>Include</th></tr></thead><tbody>
          {proposal.document.rows.map(row => {
            const choice = choices[row.row_id] || {}
            const material = proposal.materials.find(item => item.id === choice.material_id)
            const sameUnit = material?.unit === row.unit
            return <tr key={row.row_id}><td><strong>{row.name || '(Missing description)'}</strong><small>{row.code} · {row.row_id}</small><small>{row.specification}</small>
              {mapping.kind === 'client_bom' && <small>Client quantity: {row.client_quantity ?? 'Missing'} {row.unit}</small>}
              {row.reasons.map(reason => <small className="client-row-error" key={reason}>{reason}</small>)}</td>
              <td>{row.currency || 'Missing currency'} {row.unit_price ?? 'Missing price'} / {row.unit || 'Missing unit'}</td>
              <td><label>Material for {row.row_id}<select value={choice.material_id || ''} disabled={choice.excluded} onChange={event => choose(row.row_id, { material_id: event.target.value ? Number(event.target.value) : null, units_per_purchase: null })}>
                <option value="">Choose material</option>{proposal.materials.map(item => <option key={item.id} value={item.id}>{item.code} · {item.name} ({item.unit})</option>)}</select></label>
                {material && <label>Catalog units per purchase unit {row.row_id}<input type="number" min=".0001" max="100000" step=".0001" disabled={choice.excluded || sameUnit}
                  value={sameUnit ? '1' : choice.units_per_purchase || ''} onChange={event => choose(row.row_id, { units_per_purchase: event.target.value || null })} /></label>}
              </td><td><label><input type="checkbox" checked={Boolean(choice.excluded)} onChange={event => choose(row.row_id, { excluded: event.target.checked })} />Exclude {row.row_id}</label></td></tr>
          })}
        </tbody></table></div>
        <p>{validated ? proposal.ready ? 'Mappings validated.' : 'Resolve the row issues or explicitly exclude those rows.' : 'Validate mappings to refresh row issues.'}</p>
        {validated && proposal.ready && <label className="studio-confirmation"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />I reviewed these project prices, units, conversions and exclusions.</label>}
        </>}
      </fieldset>
      <Button type="button" disabled={busy || disabled || (!uncertain && !(validated && proposal?.ready && confirmed))} onClick={() => run('apply')}>
        {busy ? 'Working…' : uncertain ? 'Retry identical import' : 'Save & apply project pricing'}
      </Button>
    </details>}
    {versions.length > 0 && <label>Saved client import<select value={selectedVersion} disabled={busy} onChange={event => setSelectedVersion(event.target.value)}>
      <option value="">Choose a version</option>{versions.map(version => <option key={version.id} value={version.id}>Version {version.version_number} · {version.filename} · {version.kind === 'client_bom' ? 'Client BOM' : 'Price list'}</option>)}
    </select></label>}
    {detail && <div className="client-price-table"><table><thead><tr><th>Client item</th><th>Price</th><th>Client qty</th><th>Calculated qty</th><th>Difference</th></tr></thead><tbody>
      {detail.document.rows.filter(row => !row.excluded).map(row => {
        const comparison = detail.comparison?.find(item => item.row_id === row.row_id)
        return <tr key={row.row_id}><td>{row.name}<small>{row.specification}</small><small>{row.catalog_code} · {row.row_id}</small></td>
          <td>{row.currency} {row.unit_price} / {row.unit}</td><td>{row.client_quantity ?? 'Not supplied'}</td>
          <td>{comparison?.calculated_quantity ?? 'Unavailable'} {comparison?.calculated_quantity != null ? row.unit : ''}<small>{comparison?.reason || (!estimateId ? 'Select a saved estimate to compare.' : '')}</small></td>
          <td>{comparison?.difference ?? '—'}</td></tr>
      })}
    </tbody></table></div>}
    {message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
  </section>
}
