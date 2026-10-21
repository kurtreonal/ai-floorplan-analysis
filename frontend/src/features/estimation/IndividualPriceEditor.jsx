import { useEffect, useRef, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { Button } from '../../components/ui/button.jsx'
import { fetchItemPrices, saveIndividualPrices } from '../../api/itemPricing.js'
import { legendDescription } from '../../api/legendChoices.js'

const reference=row=>(row.symbol_ids || row.path_ids || [row.path_id]).filter(Boolean).join(', ')
export function IndividualPriceEditor({projectId,floorPlanId,disabled,onSaved}) {
  const [open,setOpen]=useState(false),[loaded,setLoaded]=useState(null),[edits,setEdits]=useState({})
  const [query,setQuery]=useState(''),[filter,setFilter]=useState('all'),[error,setError]=useState(''),[busy,setBusy]=useState(false),[uncertain,setUncertain]=useState(false)
  const request=useRef(null),pending=useRef(null)
  useEffect(()=>{
    if(!open)return
    const controller=new AbortController()
    fetchItemPrices(projectId,{signal:controller.signal}).then(data=>{
      if(controller.signal.aborted)return
      setLoaded(data);setEdits({});setError('');setUncertain(false);pending.current=null
    }).catch(failure=>{if(!controller.signal.aborted)setError(failure.message)})
    return ()=>controller.abort()
  },[open,projectId,floorPlanId])
  useEffect(()=>()=>request.current?.abort(),[])
  const rows=(loaded?.items || []).filter(row=>(!floorPlanId || row.floor_plan_id===floorPlanId)
    && (filter==='all' || row.kind===filter)
    && (row.name+' '+reference(row)).toLowerCase().includes(query.toLowerCase()))
  async function save() {
    if(busy || !loaded)return
    const selection=pending.current || {request_id:crypto.randomUUID(),expected_version:loaded.assignment_version,
      items:Object.entries(edits).map(([item_key,value])=>({item_key,unit_price:value.price,currency:value.currency}))}
    if(!selection.items.length)return
    pending.current=selection
    const controller=new AbortController();request.current=controller
    setBusy(true);setError('')
    try {
      await saveIndividualPrices(projectId,selection,{signal:controller.signal})
      if(controller.signal.aborted)return
      pending.current=null;setUncertain(false);setOpen(false);setLoaded(null);setEdits({});onSaved?.()
    } catch(failure) {
      if(!controller.signal.aborted) {
        setError(failure.message)
        const retry=!failure.status || failure.status>=500
        setUncertain(retry);if(!retry)pending.current=null
      }
    } finally {if(!controller.signal.aborted)setBusy(false)}
  }
  function change(row,key,value) {
    const previous=edits[row.item_key] || {price:String(row.unit_price ?? row.client_unit_price ?? ''),currency:row.currency || 'PHP'}
    setEdits(current=>({...current,[row.item_key]:{...previous,[key]:value}}))
  }
  return <Dialog.Root open={open} onOpenChange={value=>{if(!busy){setOpen(value);if(!value)setLoaded(null)}}}>
    <Dialog.Trigger asChild><Button variant="outline" disabled={disabled}>Edit prices</Button></Dialog.Trigger>
    <Dialog.Portal><Dialog.Overlay className="studio-sheet-overlay"/>
      <Dialog.Content className="studio-panel bom-price-dialog">
        <header><div><Dialog.Title>Edit individual prices</Dialog.Title><Dialog.Description>Change unit prices for {floorPlanId ? 'this plan':'this project'}. Quantities and saved estimates stay unchanged.</Dialog.Description></div>
          <Dialog.Close asChild><Button variant="ghost" size="icon" disabled={busy} aria-label="Close price editor"><X aria-hidden="true" size={18}/></Button></Dialog.Close></header>
        <div className="bom-price-filters"><input aria-label="Find device or path" placeholder="Find device or path…" value={query} onChange={event=>setQuery(event.target.value)}/>
          <select aria-label="Item type" value={filter} onChange={event=>setFilter(event.target.value)}><option value="all">All items</option><option value="device">Devices</option><option value="path">Wiring paths</option></select></div>
        {!loaded && !error && <p role="status">Loading prices…</p>}
        <form onSubmit={event=>{event.preventDefault();save()}}>
          <fieldset disabled={busy || uncertain}>
            <div className="bom-price-items">{rows.map(row=><div key={row.item_key} className="bom-price-item">
              <div><strong>{legendDescription(row.name)}</strong><small>{reference(row)} · {row.kind==='path' ? row.material_kind==='wire'?'Wire/cable':'Conduit':'Device'}</small></div>
              <label>Price / {row.unit==='source pixel' ? 'meter':row.unit}<input aria-label={`Price ${row.item_key}`} type="number" min="0" max="1000000000" step="any" value={edits[row.item_key]?.price ?? row.unit_price ?? row.client_unit_price ?? ''} onChange={event=>change(row,'price',event.target.value)}/></label>
              <label>Currency<input aria-label={`Currency ${row.item_key}`} maxLength={3} pattern="[A-Z]{3}" value={edits[row.item_key]?.currency ?? row.currency ?? 'PHP'} onChange={event=>change(row,'currency',event.target.value.toUpperCase())}/></label>
            </div>)}</div>
          </fieldset>
          {loaded && !rows.length && <p>No matching saved items.</p>}
          {error && <p role="alert">{error}</p>}
          <footer><Dialog.Close asChild><Button variant="ghost" disabled={busy}>Cancel</Button></Dialog.Close>
            <Button type="submit" disabled={busy || !Object.keys(edits).length || Object.values(edits).some(value=>value.price==='' || !/^[A-Z]{3}$/.test(value.currency))}>{busy ? 'Saving…':uncertain ? 'Retry save':'Save prices'}</Button></footer>
        </form>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
}
