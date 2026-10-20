import { useId, useRef, useState } from 'react'
import { groupLegendChoices } from '../../api/legendChoices.js'
import { isWiringLegend } from '../../api/symbolLegends.js'
import { deviceFamily } from './devicePresentation.js'
import { Button } from '../../components/ui/button.jsx'
import './devicePicker.css'

const normalized = value => String(value ?? '').normalize('NFKC').toLocaleLowerCase('en').replace(/[^\p{L}\p{N}]+/gu,' ').trim()
const familyName = item => item.category || item.type || deviceFamily(item.displayName).replaceAll('-',' ')
const detail = item => [item.catalog_code || item.code,item.specification,familyName(item) === 'unknown' ? null : familyName(item)].filter(Boolean).join(' · ')

export function DevicePicker({ legends, value, onChange, onCancel, disabled = false }) {
  const [query,setQuery] = useState('')
  const searchId = useId()
  const search = useRef(null), picker = useRef(null)
  const choices = groupLegendChoices(legends,{selectedId:Number(value) || null}).filter(item=>
    item.is_active !== false && !isWiringLegend(item) && deviceFamily(item.displayName) !== 'annotation')
  const words = normalized(query).split(' ').filter(Boolean)
  const matches = choices.filter(item=>{
    const text = normalized([item.displayName,detail(item),item.class_id,...item.aliases.flatMap(alias=>
      [alias.name,alias.catalog_code,alias.code,...(Array.isArray(alias.aliases) ? alias.aliases.filter(a=>typeof a === 'string') : [])])].join(' '))
    return words.every(word=>text.includes(word))
  })
  const chosen = choices.find(item=>String(item.id) === value)
  function keyboard(event) {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); onCancel?.() }
    if (event.key === 'Enter' && event.target === picker.current) { event.preventDefault(); event.stopPropagation(); picker.current?.blur() }
  }
  return <div className="studio-device-picker" onKeyDown={keyboard}>
    <label htmlFor={searchId}>Search available devices</label><div className="studio-device-search">
      <input id={searchId} ref={search} type="search" value={query} disabled={disabled} autoComplete="off"
        onChange={event=>setQuery(event.target.value)} onKeyDown={event=>{
          if (event.key === 'ArrowDown' && matches.length) {event.preventDefault();event.stopPropagation();picker.current?.focus()}
        }} />
      {query && <Button type="button" variant="ghost" disabled={disabled} aria-label="Clear device search" onClick={()=>{setQuery('');search.current?.focus()}}>Clear</Button>}
    </div>
    <label>Device to place<select ref={picker} aria-label="Device to place" size={Math.min(6,Math.max(2,matches.length+1))}
      value={value} disabled={disabled || !choices.length} onChange={event=>onChange(event.target.value)}>
      <option value="">Choose a device</option>
      {chosen && !matches.includes(chosen) && <optgroup label="Current selection"><option value={chosen.id}>{chosen.displayName} · {detail(chosen)}</option></optgroup>}
      {matches.map(item=><option key={item.id} value={item.id} title={[item.displayName,detail(item)].filter(Boolean).join(' · ')}>{[item.displayName,detail(item)].filter(Boolean).join(' · ')}</option>)}
    </select></label>
    {!matches.length && <p role="status">No matching approved devices.</p>}
    {chosen && <p role="status">Ready to place: {chosen.displayName}{detail(chosen) ? ` · ${detail(chosen)}` : ''}</p>}
  </div>
}
