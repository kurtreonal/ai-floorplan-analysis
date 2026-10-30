import {useId,useState} from 'react'

const productText=m=>`${m.brand ? m.brand+' · ':''}${m.name.replace(/^EMT pipe/i,'EMT tubing')}`

export function ConduitProductInput({products,value,onChange,disabled}) {
  const id=useId(),[search,setSearch]=useState(null),[open,setOpen]=useState(false),[active,setActive]=useState(0)
  const selected=products.find(m=>String(m.id)===String(value))
  const query=(search || '').trim().toLowerCase()
  const size=query.match(/(?:^|\s)(\d+(?:-\d+\/\d+|\/\d+|\.\d+)?)["”]?(?=\s|$)/)?.[1]
  const fraction=text=>text.includes('/') ? Number(text.split('/')[0])/Number(text.split('/')[1]):Number(text)
  const nominal=size ? size.includes('-') ? Number(size.split('-')[0])+fraction(size.split('-')[1]):fraction(size):null
  const words=query.split(/\s+/).filter(word=>word.replace(/["”]/g,'')!==size)
  const results=products.filter(m=>(nominal==null || m.nominal_inches==null || m.nominal_inches===nominal) && words.every(word=>productText(m).toLowerCase().includes(word)))
  function choose(product){onChange(String(product.id));setSearch(null);setOpen(false);setActive(0)}
  return <div className="conduit-product-input">
    <input role="combobox" aria-label="Conduit product" aria-autocomplete="list" aria-expanded={open} aria-controls={id}
      aria-activedescendant={open && results[active] ? `${id}-${results[active].id}`:undefined}
      disabled={disabled} value={search ?? (selected ? productText(selected):'')} placeholder="Find a conduit by size or brand…"
      title={selected ? productText(selected):undefined}
      onFocus={e=>{setOpen(true);setSearch(null);setActive(Math.max(0,products.findIndex(m=>String(m.id)===String(value))));e.currentTarget.select()}}
      onChange={e=>{setSearch(e.target.value);setOpen(true);setActive(0)}}
      onBlur={()=>{setOpen(false);setSearch(null)}}
      onKeyDown={e=>{
        if(e.key==='ArrowDown' || e.key==='ArrowUp'){
          e.preventDefault();setOpen(true)
          const next=e.key==='ArrowDown' ? open?Math.max(0,Math.min(active+1,results.length-1)):0:Math.max(0,active-1)
          setActive(next)
          requestAnimationFrame(()=>document.getElementById(`${id}-${results[next]?.id}`)?.scrollIntoView({block:'nearest'}))
        }
        if(e.key==='Enter' && open){e.preventDefault();if(results[active])choose(results[active])}
        if(e.key==='Escape'){e.preventDefault();setOpen(false);setSearch(null)}
      }}/>
    {open && <div id={id} role="listbox" aria-label="Available conduits" className="conduit-product-results">
      {results.map((m,index)=><button key={m.id} id={`${id}-${m.id}`} role="option" aria-selected={String(m.id)===String(value)} type="button"
        tabIndex={-1} className={index===active?'is-active':''} onMouseDown={e=>e.preventDefault()} onClick={()=>choose(m)}>
        <span>{productText(m)}</span><small>{m.currency} {Number(m.unit_price).toLocaleString('en-PH',{minimumFractionDigits:2})} / {m.unit}</small>
      </button>)}
      {!results.length && <p>No matching conduit for this wire.</p>}
    </div>}
  </div>
}
