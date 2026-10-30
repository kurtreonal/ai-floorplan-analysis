import {AdminLegendPreview} from './AdminLegendPreview.jsx'
import { useEffect,useRef, useState } from 'react'
import { importTrainedLegends, importApprovedPdfLegends, listAdminLegends, saveAdminLegend, uploadLegendArtwork, listLegendReferenceImages, saveLegendReferenceImage, setLegendAvailability } from '../../api/adminLegends.js'
import { groupLegendChoices, legendSearchText, legendDescription,legendSourceSuffix,legendDisplayName } from '../../api/legendChoices.js'
import {LegendArtworkPicker} from './LegendArtworkPicker.jsx'
import { Button } from '../../components/ui/button.jsx'
import './adminCatalog.css'

export function AdminLegendPanel() {
  const [records, setRecords] = useState([])
  const [ready, setReady] = useState(false)
  const [busy, setBusy] = useState(true)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [name, setName] = useState('')
  const [classId, setClassId] = useState('')
  const [query,setQuery]=useState('')
  const [status,setStatus]=useState('active')
  const [editing,setEditing]=useState(null)
  const [showForm,setShowForm]=useState(false)
  const [artwork,setArtwork]=useState({kind:'auto',referenceId:'',file:null})
  const [references,setReferences]=useState([]),[referenceError,setReferenceError]=useState('')
  const [previewRevision,setPreviewRevision]=useState(0)
  const locked = useRef(false)
  useEffect(()=>{const controller=new AbortController();listAdminLegends({signal:controller.signal}).then(rows=>{setRecords(rows);setReady(true)}).catch(failure=>{if(!controller.signal.aborted)setError(failure.message)}).finally(()=>{if(!controller.signal.aborted)setBusy(false)});return()=>controller.abort()},[])

  useEffect(()=>{const controller=new AbortController();listLegendReferenceImages({signal:controller.signal}).then(setReferences).catch(error=>{if(!controller.signal.aborted)setReferenceError(error.message)});return()=>controller.abort()},[])

  async function load() {
    if (locked.current) return
    locked.current = true; setBusy(true); setError('')
    try { setRecords(await listAdminLegends()); setReady(true);setPreviewRevision(value=>value+1) }
    catch { setReady(false); setError('Could not load the Admin catalog. Check your session and reload.') }
    finally { locked.current = false; setBusy(false) }
  }

  async function save(record) {
    if (locked.current || !ready) return
    locked.current = true; setBusy(true); setError(''); setMessage('')
    try {
      if(record){
        setRecords(await setLegendAvailability((record.aliases || [record]).map(row=>row.id),!record.is_active))
        setMessage(`${record.displayName || legendDescription(record.name)} ${record.is_active?'hidden from':'available in'} the designer library.`)
        return
      }
      const suffix=editing?legendSourceSuffix(editing.name):''
      const body={class_id:Number(classId),name:name.trim()+(suffix?' '+suffix:''),is_active:editing?.is_active ?? true}
      if(classId.trim()==='')throw new Error('Reload the catalog before adding a legend.')
      if(artwork.kind==='pec'&&!artwork.referenceId)throw new Error('Choose a PEC device symbol.')
      if(artwork.kind==='upload'&&!artwork.file)throw new Error('Choose an image file to upload.')
      const saved=await saveAdminLegend(body,editing?.id)
      setRecords(current=>[...current.filter(row=>row.id!==saved.id),saved].sort((a,b)=>a.class_id-b.class_id))
      const key=value=>legendDisplayName(value).normalize('NFKC').trim().replace(/\s+/g,' ').toLowerCase()
      const aliases=(editing?.aliases || [saved]).filter(row=>row.id===saved.id || key(row.name)===key(saved.name))
      if(artwork.kind!=='auto'){
        setEditing({...saved,aliases});setClassId(String(saved.class_id))
        if(artwork.kind==='pec')await saveLegendReferenceImage(saved.id,artwork.referenceId,aliases.map(row=>row.id))
        else await uploadLegendArtwork(saved.id,artwork.file,aliases.map(row=>row.id))
        setPreviewRevision(value=>value+1)
      }
      setName('');setClassId('');setEditing(null);setShowForm(false);setArtwork({kind:'auto',referenceId:'',file:null})
      setMessage(`${legendDescription(saved.name)} saved.`)
    } catch (failure) { setError(failure.message || 'Save failed. Reload before retrying.') }
    finally { locked.current = false; setBusy(false) }
  }

  async function importTrainingCatalog(pdf = false) {
    if (locked.current || !ready) return
    locked.current = true; setBusy(true); setError(''); setMessage('')
    try {
      await (pdf ? importApprovedPdfLegends() : importTrainedLegends())
      setRecords(await listAdminLegends());setPreviewRevision(value=>value+1)
      setMessage(`${pdf?'Drawing':'Trained'} library combined. Existing entries and images kept; missing PEC symbols added where matched.`)
    } catch (failure) { setError(failure.message || 'Import failed. Reload before retrying.') }
    finally { locked.current = false; setBusy(false) }
  }

  const grouped=groupLegendChoices(records,{combineInactive:true}).map((record,index)=>({...record,number:index+1}))
  const visible=grouped.filter(record=>(status==='all' || record.is_active===(status==='active'))
    && legendSearchText(record.displayName).includes(legendSearchText(query)))
  function edit(record=null){setArtwork({kind:'auto',referenceId:'',file:null});setEditing(record);setName(record ? legendDescription(record.name):'');setClassId(String(record?.class_id ?? Math.max(-1,...records.map(r=>r.class_id))+1));setShowForm(true)}
  return <section className="studio-panel admin-catalog" aria-label="Admin symbol legends" id="admin-legends">
    <div className="studio-panel-heading"><h2>Device legends</h2>
    <Button disabled={busy || !ready} onClick={()=>edit()}>Add legend</Button></div>
    <p>One entry per device meaning. Edit its symbol image or add a manual legend.</p><small>{grouped.length} device and wiring entries in the combined library.</small>
    <>
      <div className="admin-catalog-toolbar"><input type="search" aria-label="Search device legends" placeholder="Search devices…" value={query} onChange={event=>setQuery(event.target.value)}/>
        <select aria-label="Legend status" value={status} onChange={event=>setStatus(event.target.value)}><option value="active">Active</option><option value="inactive">Inactive</option><option value="all">All</option></select>

        <Button variant="ghost" disabled={busy} onClick={load}>Reload</Button></div>
      {showForm && <form className="project-floor-create-form" onSubmit={event => {event.preventDefault(); save()}}>
        <label>Legend name<input required maxLength={255} value={name} disabled={busy || !ready} onChange={event => setName(event.target.value)} /></label>
        <LegendArtworkPicker value={artwork} onChange={setArtwork} references={references} referenceError={referenceError} editing={Boolean(editing)} disabled={busy}/>
        {editing?.aliases?.length>1 && <small>This image will be used for all {editing.aliases.length} matching copies of this legend.</small>}
        <Button disabled={busy || !ready} type="submit">{editing ? 'Save device':'Add active legend'}</Button>
        <Button variant="ghost" type="button" onClick={()=>{setArtwork({kind:'auto',referenceId:'',file:null});setShowForm(false)}}>Cancel</Button>
      </form>}
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <div className="studio-table-scroll"><table className="studio-estimate-table"><thead><tr><th>No.</th><th>Device</th><th>Status</th><th>Actions</th></tr></thead><tbody>
      {visible.map(record=><tr key={record.id}><td>{record.number}</td><td title={record.displayName}><div className="admin-legend-identity"><AdminLegendPreview key={`${record.id}:${previewRevision}`} id={record.id} aliases={record.aliases} revision={previewRevision}/><span>{record.displayName}</span></div></td><td>{record.is_active ? 'Active':'Inactive'}</td><td>
        <Button variant="ghost" disabled={busy || !ready} onClick={()=>edit(record)}>Edit</Button>
        <Button variant="ghost" disabled={busy || !ready} onClick={()=>save(record)}>{record.is_active?'Deactivate':'Activate'}</Button>
      </td></tr>)}
      </tbody></table></div>
      {busy && !ready && <p role="status">Loading device legends…</p>}{ready && !visible.length && <p>No legends match these filters.</p>}
      <section className="admin-catalog-tools" aria-label="Combine legend sources"><h3>Add source libraries</h3><p>These combine with the current library. Duplicate names are shown once; their source links are retained.</p>
        <Button variant="outline" disabled={busy || !ready || showForm} onClick={() => importTrainingCatalog()}>Import trained legends</Button>
        <Button variant="outline" disabled={busy || !ready || showForm} onClick={() => importTrainingCatalog(true)}>Import approved drawing legends</Button>
        <small>Saved drawings are unchanged. Importing does not retrain the detector.</small>
      </section>
    </>
  </section>
}
