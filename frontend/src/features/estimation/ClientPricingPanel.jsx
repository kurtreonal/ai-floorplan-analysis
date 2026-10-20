import { useEffect, useRef, useState } from 'react'
import { applyProjectPrices, fetchProjectPrice, listProjectPrices, previewProjectPrices } from '../../api/projectPricing.js'
import { Button } from '../../components/ui/button.jsx'
import './clientPricing.css'

export function ClientPricingPanel({ projectId, designer, disabled = false, estimateId, onVersionsChange, onApplied, defaultImportOpen = false }) {
  const [importOpen, setImportOpen] = useState(defaultImportOpen)
  const [busy, setBusy] = useState(false)
  const [uncertain, setUncertain] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [versions, setVersions] = useState([])
  const [selectedVersion, setSelectedVersion] = useState('')
  const [detailResult, setDetailResult] = useState(null)
  const [refresh, setRefresh] = useState(0)
  const controller = useRef(null)
  const retry = useRef(null)
  const input = useRef(null)
  const inFlight = useRef(false)
  const detail = detailResult?.version === selectedVersion && detailResult?.estimateId === estimateId ? detailResult.value : null

  useEffect(() => {
    const request = new AbortController()
    listProjectPrices(projectId, { signal: request.signal }).then(rows => {
      if (request.signal.aborted) return
      setVersions(rows); onVersionsChange?.(rows)
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

  async function upload(file) {
    if (!file || !designer || disabled || inFlight.current) return
    inFlight.current = true
    const request = new AbortController(); controller.current = request
    setBusy(true); setError(''); setMessage('')
    try {
      let attempt = retry.current
      if (!attempt) {
        const proposal = await previewProjectPrices(projectId, file, null, { signal: request.signal })
        if (request.signal.aborted) return
        if (!proposal.ready) throw new Error('The file could not be matched. Check material codes, units and prices, then upload again.')
        attempt = { file, payload: {
          automatic: true, mapping: proposal.document.mapping,
          choices: proposal.document.rows.map(row => ({ row_id: row.row_id, material_id: row.material_id,
            units_per_purchase: row.units_per_purchase, excluded: row.excluded })),
          request_id: crypto.randomUUID(), confirmed: true, file_sha256: proposal.file_sha256,
          preview_token: proposal.preview_token, expected_version: proposal.expected_version,
        } }
        retry.current = attempt
      }
      const value = await applyProjectPrices(projectId, attempt.file, attempt.payload, { signal: request.signal })
      if (request.signal.aborted) return
      retry.current = null; setUncertain(false); setRefresh(current => current + 1)
      onApplied?.(value)
      setMessage('Prices updated. Saved estimates are unchanged.')
      if (input.current) input.current.value = ''
    } catch (failure) {
      if (!request.signal.aborted) {
        if (retry.current && (!failure.status || failure.status >= 500)) {
          setUncertain(true)
          setError('Couldn’t confirm the upload. Retry to check without applying it twice.')
        } else {
          retry.current = null; setUncertain(false); setError(failure.message)
          if (input.current) input.current.value = ''
        }
      }
    } finally { inFlight.current = false; if (!request.signal.aborted) setBusy(false) }
  }

  return <section className="studio-panel client-pricing" aria-labelledby="client-pricing-title">
    <div className="studio-panel-heading"><h2 id="client-pricing-title">Client BOM pricing</h2></div>
    {designer && <details open={importOpen} onToggle={event => setImportOpen(event.currentTarget.open)}>
      <summary>Upload BOM pricing (XLSX or CSV)</summary>
      <p>Choose a file to update matching material prices automatically.</p>
      <label>Client file<input ref={input} type="file" accept=".xlsx,.csv" disabled={busy || disabled || uncertain}
        onChange={event => { const file = event.target.files?.[0]; if (!uncertain) upload(file) }} /></label>
      {uncertain && <Button type="button" disabled={busy || disabled} onClick={() => upload(retry.current?.file)}>Retry upload</Button>}
      {busy && <p role="status">Updating prices…</p>}
    </details>}
    {versions.length > 0 && <details><summary>Previous uploads</summary>
      <label>Saved client import<select value={selectedVersion} disabled={busy} onChange={event => setSelectedVersion(event.target.value)}>
        <option value="">Choose a version</option>{versions.map(version => <option key={version.id} value={version.id}>Version {version.version_number} · {version.filename}</option>)}
      </select></label>
      {detail && <div className="client-price-table"><table><thead><tr><th>Client item</th><th>Price</th><th>Client qty</th><th>Calculated qty</th><th>Difference</th></tr></thead><tbody>
        {detail.document.rows.filter(row => !row.excluded).map(row => {
          const comparison = detail.comparison?.find(item => item.row_id === row.row_id)
          return <tr key={row.row_id}><td>{row.name}<small>{row.specification}</small><small>{row.catalog_code} · {row.row_id}</small></td>
            <td>{row.currency} {row.unit_price} / {row.unit}</td><td>{row.client_quantity ?? 'Not supplied'}</td>
            <td>{comparison?.calculated_quantity ?? 'Unavailable'} {comparison?.calculated_quantity != null ? row.unit : ''}<small>{comparison?.reason || (!estimateId ? 'Select a saved estimate to compare.' : '')}</small></td>
            <td>{comparison?.difference ?? '—'}</td></tr>
        })}
      </tbody></table></div>}
    </details>}
    {message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
  </section>
}
