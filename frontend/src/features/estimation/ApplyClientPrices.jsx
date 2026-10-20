import { useEffect, useRef, useState } from 'react'
import { listProjectPrices, fetchProjectPrice } from '../../api/projectPricing.js'
import { fetchItemPrices, previewItemPrices, applyItemPrices } from '../../api/itemPricing.js'
import { Button } from '../../components/ui/button.jsx'
import './clientPricing.css'

const money = (amount, currency) => amount == null ? '—' : new Intl.NumberFormat(undefined, {style:'currency',currency}).format(Number(amount))

export function ApplyClientPrices({ projectId, floorId, disabled = false, onApplied }) {
  const [input, setInput] = useState({version:'',row:'',scope:floorId ? `floor:${floorId}` : 'project',keys:[],mode:'selected'})
  const [loaded, setLoaded] = useState(null)
  const [open, setOpen] = useState(false)
  const [priceDetail, setPriceDetail] = useState(null)
  const [filter, setFilter] = useState({query:'',kind:''})
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)
  const [uncertain, setUncertain] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [refresh, setRefresh] = useState(0)
  const attempt = useRef(null)
  const controller = useRef(null)
  const inFlight = useRef(false)
  useEffect(() => {
    if (!open) return
    const request = new AbortController()
    Promise.all([fetchItemPrices(projectId,{signal:request.signal}),listProjectPrices(projectId,{signal:request.signal})])
      .then(([inventory,versions]) => { if (!request.signal.aborted) setLoaded({inventory,versions}) })
      .catch(failure => { if (!request.signal.aborted) setError(failure.message) })
    return () => request.abort()
  },[projectId,refresh,open])
  useEffect(() => {
    const request = new AbortController()
    if (input.version) fetchProjectPrice(projectId,input.version,{signal:request.signal})
      .then(value => { if (!request.signal.aborted) setPriceDetail(value) })
      .catch(failure => { if (!request.signal.aborted) setError(failure.message) })
    return () => request.abort()
  },[projectId,input.version])
  useEffect(() => () => controller.current?.abort(),[])
  const entries = String(priceDetail?.id) === input.version ? priceDetail.document.rows.filter(row=>!row.excluded) : []
  const entry = entries.find(row=>row.row_id === input.row)
  const currentFloor = input.scope.startsWith('floor:') ? Number(input.scope.slice(6)) : null
  const items = (loaded?.inventory.items || []).filter(row=>!currentFloor || row.floor_id === currentFloor)
  const visible = items.filter(row=>(!filter.kind || (row.kind === 'device' ? 'device' : 'path') === filter.kind) &&
    [row.name,...(row.symbol_ids || []),row.material_name,row.item_kind].join(' ').toLowerCase().includes(filter.query.toLowerCase()))
  const locked = busy || disabled || uncertain
  function change(values) { setInput(current=>({...current,...values})); setPreview(null); setError(''); setMessage('') }
  const selection = {price_version_id:Number(input.version),price_row_id:input.row,scope:currentFloor ? 'floor':'project',
    floor_id:currentFloor,mode:input.mode,item_keys:input.mode === 'selected' ? input.keys : []}
  async function run(apply = false) {
    if (inFlight.current || disabled) return
    inFlight.current = true
    const request = new AbortController(); controller.current = request
    setBusy(true); setError(''); setMessage('')
    try {
      if (!apply) {
        const value = await previewItemPrices(projectId,selection,{signal:request.signal})
        if (!request.signal.aborted) setPreview(value)
      } else {
        const payload = attempt.current || {...selection,request_id:crypto.randomUUID(),preview_token:preview.preview_token}
        attempt.current = payload
        await applyItemPrices(projectId,payload,{signal:request.signal})
        if (!request.signal.aborted) {
          attempt.current = null; setUncertain(false); setPreview(null); setInput(current=>({...current,keys:[],mode:'selected'}))
          setMessage('Selected prices applied. Quantities and saved estimates are unchanged.')
          setRefresh(current=>current+1); onApplied?.()
        }
      }
    } catch (failure) {
      if (!request.signal.aborted) {
        const uncertain = apply && (!failure.status || failure.status >= 500)
        setUncertain(uncertain)
        if (!uncertain) { attempt.current = null; if (apply) setPreview(null) }
        setError(uncertain ? 'Couldn’t confirm the change. Retry safely without applying twice.' : failure.message)
      }
    } finally { inFlight.current = false; if (!request.signal.aborted) setBusy(false) }
  }
  return <details className="client-pricing item-pricing" open={open} onToggle={event=>setOpen(event.currentTarget.open)}><summary>Apply client prices to selected items</summary>
    <p>Saved devices and wiring paths. Each wiring path includes wire/cable and conduit; their products and prices are separate. Save canvas edits first.</p>
    {open && <><fieldset disabled={locked || !loaded}>
      <div className="item-price-controls">
        <label>Client price list<select value={input.version} onChange={event=>change({version:event.target.value,row:'',keys:[]})}>
          <option value="">Choose an uploaded version</option>{loaded?.versions.map(row=><option key={row.id} value={row.id}>Version {row.version_number} · {row.filename}</option>)}
        </select></label>
        <label>Client price entry<select value={input.row} onChange={event=>change({row:event.target.value,keys:[],mode:'selected'})}>
          <option value="">Choose a compatible entry</option>{entries.map(row=><option key={row.row_id} value={row.row_id}>{[row.catalog_code,row.name,row.specification,`${money(row.unit_price,row.currency)} / ${row.unit}`].filter(Boolean).join(' · ')}</option>)}
        </select></label>
        <label>Apply scope<select value={input.scope} onChange={event=>change({scope:event.target.value,keys:[],mode:'selected'})}>
          <option value="project">Entire project</option>{loaded?.inventory.floors.map(id=><option key={id} value={`floor:${id}`}>Floor {id}</option>)}
        </select></label>
      </div>
      <div className="item-price-controls"><label>Search saved items<input type="search" value={filter.query} onChange={event=>setFilter({...filter,query:event.target.value})}/></label>
        <label>Item type<select value={filter.kind} onChange={event=>setFilter({...filter,kind:event.target.value})}>
          <option value="">All types</option><option value="device">Devices</option><option value="path">Wiring paths</option>
        </select></label></div>
      <div className="client-price-table"><table aria-label="Saved items for pricing"><thead><tr><th>Select</th><th>Item</th><th>Unit / current price</th></tr></thead><tbody>
        {visible.map(row=><tr key={row.item_key}><td><input type="checkbox" aria-label={`Price ${row.name} ${row.symbol_ids?.join(', ') || row.path_id || row.item_kind}`}
          disabled={!entry || row.material_id !== entry.material_id} checked={input.keys.includes(row.item_key)} onChange={event=>change({mode:'selected',keys:event.target.checked ? [...input.keys,row.item_key] : input.keys.filter(key=>key !== row.item_key)})}/></td>
          <td>{row.name}<small>{row.kind === 'path' ? `Wiring path · ${row.material_kind === 'wire' || row.item_kind === 'wire' ? 'Wire/cable' : row.material_kind === 'conduit' || row.item_kind === 'conduit' ? 'Conduit' : 'Material not assigned'}` : 'Device'}</small><small>{row.material_name}</small><small>{row.symbol_ids?.join(', ') || row.path_id || row.item_kind} · {row.floor_id ? `Floor ${row.floor_id}`:'Project route'}</small>
            {(!entry || row.material_id !== entry.material_id) && <small>{!entry ? 'Choose a price entry.' : !row.material_id ? 'Choose the matching product/size for this item first.' : 'This price entry is for a different product/size.'}</small>}</td>
          <td>{row.quantity} {row.unit}<small>{money(row.unit_price,row.currency)} / {row.unit}</small></td></tr>)}
      </tbody></table>{!visible.length && <p>No matching saved items.</p>}</div>
      <div className="item-price-actions"><Button type="button" variant="outline" disabled={!entry || !input.keys.length} onClick={()=>run()}>Preview selected ({input.keys.length})</Button>
        <Button type="button" variant="outline" disabled={!entry} onClick={()=>change({mode:'all_wiring',keys:[]})}>Apply to all existing wirings</Button>
        {input.mode === 'all_wiring' && <Button type="button" onClick={()=>run()}>Preview wiring scope</Button>}</div>
    </fieldset>
    {preview && <section aria-label="Price application preview"><p>{preview.affected.length} compatible items · {preview.skipped.length} skipped · {currentFloor ? `Floor ${currentFloor}`:'Entire project'}. New items are not included.</p>
      <div className="client-price-table"><table><thead><tr><th>Item</th><th>Quantity</th><th>Previous price</th><th>Client price</th><th>Previous total</th><th>New total</th></tr></thead><tbody>
        {preview.affected.map(row=><tr key={row.item_key}><td>{row.name}</td><td>{row.quantity} {row.unit}</td><td>{money(row.previous_price,row.previous_currency)}</td><td>{money(row.unit_price,row.currency)} / {row.unit}</td><td>{money(row.previous_total,row.previous_currency)}</td><td>{money(row.line_total,row.currency)}</td></tr>)}
      </tbody></table></div>
      {preview.skipped.length > 0 && <details><summary>Skipped items ({preview.skipped.length})</summary><ul>{preview.skipped.map(row=><li key={row.item_key}>{row.name}: {row.reason}</li>)}</ul></details>}
      <Button type="button" disabled={busy || disabled || !preview.ready} onClick={()=>run(true)}>{uncertain ? 'Retry price application':`Apply prices to ${preview.affected.length} ${preview.affected.length === 1 ? 'item':'items'}`}</Button>
    </section>}
    {busy && <p role="status">Updating price selection…</p>}
    {message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
    </>}
  </details>
}
