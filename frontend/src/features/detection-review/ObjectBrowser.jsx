import { useId, useMemo, useRef, useState } from 'react'
import { orderNamed } from '../../utils/listOrder.js'
import './objectBrowser.css'

const sections = [
  { kind: 'symbol', label: 'Devices' },
  { kind: 'wiring', label: 'Wiring' },
  { kind: 'wall', label: 'Walls' },
]
const normalize = value => String(value ?? '').normalize('NFKC').toLocaleLowerCase('en').trim()

// Search is a view over the complete draft, never a replacement for its arrays.
export function ObjectBrowser({ draft, presentations = {}, selected, onSelect, disabled = false }) {
  const id = useId()
  const tabs = useRef([])
  const searchInput = useRef(null)
  const [kind, setKind] = useState('symbol')
  const [queries, setQueries] = useState({ symbol: '', wiring: '', wall: '' })
  const rows = useMemo(() => orderNamed((draft[`${kind}s`] ?? []).map(item => {
    const presentation = kind === 'symbol' ? presentations[item.id] : null
    const label = presentation?.label || item.name || item.label || (kind === 'symbol' ? 'Device' : kind === 'wiring' ? 'Wire' : 'Wall')
    const circuit = kind === 'wiring' ? item.circuit_id ?? item.circuit_ref : null
    const fields = kind === 'symbol'
      ? [item.id, label, item.type, item.class_name, presentation?.name, presentation?.family, presentation?.originalLabel]
      : [item.id, label, circuit]
    return { id: item.id, item, label, circuit, search: normalize(fields.filter(value => value != null).join(' ')) }
  }), row => row.label), [draft, presentations, kind])
  const words = normalize(queries[kind]).split(/\s+/).filter(Boolean)
  const matches = rows.filter(row => words.every(word => row.search.includes(word)))

  return <section className="studio-object-browser" aria-label="Find objects">
    <div role="tablist" aria-label="Object types">
      {sections.map((section, index) => <button type="button" role="tab" key={section.kind}
        id={`${id}-${section.kind}-tab`} aria-controls={`${id}-${section.kind}-panel`}
        aria-selected={kind === section.kind} tabIndex={kind === section.kind ? 0 : -1}
        ref={element => { tabs.current[index] = element }} onClick={() => setKind(section.kind)}
        onKeyDown={event => {
          const next = event.key === 'ArrowRight' ? (index + 1) % sections.length
            : event.key === 'ArrowLeft' ? (index + sections.length - 1) % sections.length
              : event.key === 'Home' ? 0 : event.key === 'End' ? sections.length - 1 : null
          if (next == null) return
          event.preventDefault()
          event.stopPropagation()
          setKind(sections[next].kind)
          tabs.current[next]?.focus()
        }}>{section.label}</button>)}
    </div>
    {sections.map(section => <div key={section.kind} role="tabpanel" hidden={kind !== section.kind}
      id={`${id}-${section.kind}-panel`} aria-labelledby={`${id}-${section.kind}-tab`}>
      {kind === section.kind && <>
        <label htmlFor={`${id}-search`}>Search {section.label.toLowerCase()}</label>
        <div className="studio-object-search">
          <input ref={searchInput} id={`${id}-search`} type="search" value={queries[kind]} autoComplete="off"
            onChange={event => setQueries(current => ({ ...current, [kind]: event.target.value }))} />
          {queries[kind] && <button type="button" aria-label={`Clear ${section.label.toLowerCase()} search`}
            onClick={() => { setQueries(current => ({ ...current, [kind]: '' })); searchInput.current?.focus() }}>Clear</button>}
        </div>
        <small>{matches.length} of {rows.length}</small>
        <ul aria-label={`${section.label} results`}>
          {matches.map(({ item, label, circuit }) => <li key={item.id}>
            <button type="button" disabled={disabled} aria-pressed={selected?.kind === kind && selected.id === item.id}
              onClick={() => onSelect({ kind, id: item.id })}>
              <span>{label}</span>
              <small>{item.id}{circuit != null && circuit !== '' ? ` · ${circuit}` : ''}{item.disposition === 'rejected' ? ' · Removed' : ''}</small>
            </button>
          </li>)}
        </ul>
        {!matches.length && <p>No matching {section.label.toLowerCase()}.</p>}
      </>}
    </div>)}
  </section>
}
