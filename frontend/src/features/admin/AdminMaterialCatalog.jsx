import { useEffect,useRef,useState } from 'react'
import { adminMaterialCatalog,saveAdminMaterialPrice } from '../../api/materialPrices.js'
import { Button } from '../../components/ui/button.jsx'
import { legendSearchText } from '../../api/legendChoices.js'
import './adminCatalog.css'
import {CatalogItemForm} from './CatalogItemForm.jsx'

export function AdminMaterialCatalog({onImport,onOpenAssemblies}){
  const [rows,setRows]=useState([]),[query,setQuery]=useState(''),[error,setError]=useState(''),[editing,setEditing]=useState(null),[busy,setBusy]=useState(false),[message,setMessage]=useState('')
  const [adding,setAdding]=useState(false),[category,setCategory]=useState('all'),[page,setPage]=useState(0),[loading,setLoading]=useState(true)
  const tableRef=useRef(null)
  useEffect(()=>{const request=new AbortController();adminMaterialCatalog({signal:request.signal}).then(setRows).catch(failure=>{if(!request.signal.aborted)setError(failure.message)}).finally(()=>{if(!request.signal.aborted)setLoading(false)});return()=>request.abort()},[])
  async function reload(){setError('');try{setRows(await adminMaterialCatalog());setEditing(null)}catch(failure){setError(failure.message)}}
  async function save(event){event.preventDefault();if(busy)return
    const data=new FormData(event.currentTarget);setBusy(true);setError('');setMessage('')
    try{await saveAdminMaterialPrice(editing,{unit_price:data.get('price'),currency:data.get('currency')});setMessage('Price saved. Existing estimates are unchanged.');await reload()}
    catch(failure){setError(failure.message)}finally{setBusy(false)}}
  const visible=rows.filter(row=>(category==='all' || row.category===category) && legendSearchText(`${row.name} ${row.code} ${row.category}`).includes(legendSearchText(query)))
  const pageSize=40,pageCount=Math.max(1,Math.ceil(visible.length/pageSize)),currentPage=Math.min(page,pageCount-1),start=currentPage*pageSize
  function changePage(next){setPage(next);tableRef.current?.scrollTo({top:0})}
  return <section className="studio-panel admin-catalog" aria-label="Approved material catalog"><div className="studio-panel-heading"><div><h2>Current catalog</h2><p>Products and purchase prices used by VED.</p></div><div className="account-actions"><Button variant="outline" disabled={busy} onClick={onImport}>Import Excel</Button><Button disabled={busy} onClick={()=>{setAdding(true);setEditing(null)}}>Add catalog item</Button></div></div>
    {adding && <CatalogItemForm onCancel={()=>setAdding(false)} onSaved={row=>{setRows(current=>[...current.filter(item=>item.id!==row.id),row].sort((a,b)=>a.name.localeCompare(b.name)));setAdding(false);setQuery(row.code);setCategory('all');setPage(0);setMessage('Catalog item added. Use Device assemblies or Wire & conduit to include it in compatible choices.')}}/>}
    <div className="admin-catalog-toolbar"><input type="search" aria-label="Search current materials" placeholder="Search products, brands or item numbers" value={query} onChange={event=>{setQuery(event.target.value);setPage(0)}}/><select aria-label="Material category" value={category} onChange={event=>{setCategory(event.target.value);setPage(0)}}><option value="all">All categories</option>{[...new Set(rows.map(row=>row.category))].sort().map(value=><option key={value}>{value}</option>)}</select><Button variant="ghost" disabled={busy || loading} onClick={reload}>Refresh</Button><small>{visible.length} items</small></div>
    {editing && <form key={editing.id} className="admin-catalog-toolbar" onSubmit={save}><strong>{editing.name}</strong><label>Price / {editing.unit}<input name="price" aria-label="Unit price" type="number" min="0" step="0.0001" required defaultValue={editing.unit_price ?? ''}/></label><label>Currency<select name="currency" defaultValue={editing.currency || 'PHP'}><option>PHP</option><option>USD</option></select></label><Button type="submit" disabled={busy}>Save price</Button><Button variant="ghost" type="button" disabled={busy} onClick={()=>setEditing(null)}>Cancel</Button></form>}
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    <div className="material-import-table" ref={tableRef}><table><thead><tr><th>Material</th><th>Unit</th><th>Price</th><th><span className="sr-only">Action</span></th></tr></thead><tbody>{visible.slice(start,start+pageSize).map(row=><tr key={row.id}><td><strong>{row.name}</strong><small className="admin-item-meta">{row.code} / {row.category}</small>{!row.is_active && <small>Inactive</small>}</td><td>{row.unit}</td><td>{row.unit_price===null?'—':`${row.currency} ${Number(row.unit_price).toLocaleString('en-PH',{minimumFractionDigits:2,maximumFractionDigits:4})}`}</td><td><Button variant="ghost" title={row.is_assembly?'Change its parts in Device assemblies':undefined} disabled={busy || !row.is_active} onClick={()=>{if(row.is_assembly){onOpenAssemblies?.();return}setAdding(false);setEditing(row);setMessage('')}}>{row.is_assembly?'Edit assembly':'Edit price'}</Button></td></tr>)}</tbody></table></div>
    {visible.length>0 && <nav className="admin-pagination" aria-label="Catalog pages"><small role="status">{start+1}–{Math.min(start+pageSize,visible.length)} of {visible.length} items</small><Button variant="outline" disabled={currentPage===0} onClick={()=>changePage(currentPage-1)}>Previous</Button><span>Page {currentPage+1} of {pageCount}</span><Button variant="outline" disabled={currentPage+1===pageCount} onClick={()=>changePage(currentPage+1)}>Next</Button></nav>}
    {loading && <p role="status">Loading materials…</p>}{!loading && !visible.length && !error && <p>No matching materials.</p>}
  </section>
}
