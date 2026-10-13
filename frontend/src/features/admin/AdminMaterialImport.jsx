import { useEffect, useRef, useState } from 'react'
import { importMaterialPrices } from '../../api/materialPrices.js'
import { orderNamed, orderList } from '../../utils/listOrder.js'
import { Button } from '../../components/ui/button.jsx'
import './materialImport.css'

export function AdminMaterialImport() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [selection, setSelection] = useState({})
  const [currency, setCurrency] = useState('PHP')
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const request = useRef(null)
  useEffect(() => () => request.current?.abort(), [])
  async function run(apply = false) {
    if (!file || busy || (apply && (!confirmed || !Object.keys(selection).length))) return
    const controller = new AbortController(); request.current = controller
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await importMaterialPrices(file, apply ? { file_sha256: preview.file_sha256,
        currency, expected_versions: selection, confirmed: true } : null, { signal: controller.signal })
      if (controller.signal.aborted) return
      if (apply) {
        setPreview(null); setSelection({}); setConfirmed(false)
        setMessage(`Imported: ${result.created} new materials, ${result.updated} price revisions, ${result.unchanged} unchanged. Existing estimates retain their prices.`)
      } else {
        setPreview(result); setConfirmed(false)
        setSelection(Object.fromEntries(result.rows.filter((row) => row.eligible).map((row) => [row.row_id, row.version])))
      }
    } catch (failure) {
      if (!controller.signal.aborted) {
        setError(failure.message)
        // An uncertain apply must be freshly previewed, not blindly replayed.
        if (apply) { setPreview(null); setSelection({}); setConfirmed(false) }
      }
    } finally { if (!controller.signal.aborted) setBusy(false) }
  }
  return <section className="studio-panel material-import" aria-labelledby="material-prices-title">
    <div className="studio-panel-heading"><h2 id="material-prices-title">Material prices</h2><span className="mono">ADMIN</span></div>
    <p>Import device, wire and conduit prices from Excel. Preview first; applying adds price history.</p>
    <label className="studio-field">Price workbook (.xlsx)<input type="file" accept=".xlsx" disabled={busy} onChange={(event) => {
      setFile(event.target.files?.[0] || null); setPreview(null); setSelection({}); setConfirmed(false); setError(''); setMessage('')
    }} /></label>
    <Button disabled={!file || busy} onClick={() => run()}>{busy ? 'Working…' : 'Preview prices'}</Button>
    {preview && <>
      <p>{preview.rows.filter((row) => row.eligible).length} eligible · {preview.issues.length + preview.rows.filter((row) => !row.eligible).length} skipped · {Object.keys(selection).length} selected</p>
      <p className="studio-panel-note">Source prices may be historical. Units remain as quoted; roll/length sizes are not assumed. Formulas and TBA prices are skipped.</p>
      <label className="studio-field">Import currency<select value={currency} disabled={busy} onChange={(event) => { setCurrency(event.target.value); setConfirmed(false) }}><option>PHP</option><option>USD</option></select></label>
      <label><input type="checkbox" disabled={busy} checked={preview.rows.some((row) => row.eligible) && Object.keys(selection).length === preview.rows.filter((row) => row.eligible).length}
        onChange={(event) => { setSelection(event.target.checked ? Object.fromEntries(preview.rows.filter((row) => row.eligible).map((row) => [row.row_id, row.version])) : {}); setConfirmed(false) }} />Select all eligible prices</label>
      <div className="material-import-table"><table><thead><tr><th>Import</th><th>Material</th><th>Unit</th><th>Previous</th><th>New price</th></tr></thead><tbody>{orderNamed(preview.rows).map((row) => <tr key={row.row_id}>
        <td><input aria-label={`Import ${row.row_id}`} type="checkbox" disabled={busy || !row.eligible} checked={row.row_id in selection} onChange={(event) => {
          setSelection((current) => { const next = { ...current }; if (event.target.checked) next[row.row_id] = row.version; else delete next[row.row_id]; return next }); setConfirmed(false)
        }} /></td><td><strong>{row.name}</strong><small>{row.code} · {row.row_id}{row.reason ? ` · ${row.reason}` : ''}</small></td>
        <td>{row.unit}</td><td>{row.current_price === null ? 'Unpriced' : `${row.current_currency} ${row.current_price}`}</td><td>{currency} {row.unit_price}</td>
      </tr>)}</tbody></table></div>
      {preview.issues.length > 0 && <details><summary>Skipped rows ({preview.issues.length})</summary><ul>{orderList(preview.issues, row => row.row_id).map((row) => <li key={row.row_id}>{row.row_id}: {row.reason}</li>)}</ul></details>}
      <label className="studio-confirmation"><input type="checkbox" disabled={busy} checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />I reviewed the selected prices, currency and purchase units.</label>
      <Button disabled={busy || !confirmed || !Object.keys(selection).length} onClick={() => run(true)}>Apply selected prices</Button>
    </>}
    {message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
  </section>
}
