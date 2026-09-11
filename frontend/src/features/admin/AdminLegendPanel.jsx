import { useRef, useState } from 'react'
import { listAdminLegends, saveAdminLegend } from '../../api/adminLegends.js'

export function AdminLegendPanel() {
  const [open, setOpen] = useState(false)
  const [records, setRecords] = useState([])
  const [ready, setReady] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [name, setName] = useState('')
  const [classId, setClassId] = useState('')
  const locked = useRef(false)

  async function load() {
    if (locked.current) return
    locked.current = true; setBusy(true); setError('')
    try { setRecords(await listAdminLegends()); setReady(true) }
    catch { setReady(false); setError('Could not load the Admin catalog. Check your session and reload.') }
    finally { locked.current = false; setBusy(false) }
  }

  async function save(record) {
    if (locked.current || !ready) return
    locked.current = true; setBusy(true); setError(''); setMessage('')
    try {
      const body = record ? {class_id:record.class_id, name:record.name, is_active:!record.is_active}
        : {class_id:Number(classId), name:name.trim(), is_active:true}
      if (!record && classId.trim() === '') throw new Error('Enter a class number.')
      const saved = await saveAdminLegend(body, record?.id)
      setRecords(current => [...current.filter(item => item.id !== saved.id), saved].sort((a,b) => a.class_id-b.class_id))
      if (!record) { setName(''); setClassId('') }
      setMessage(`${saved.name}: ${saved.is_active ? 'active' : 'inactive'}.`)
    } catch (failure) { setError(failure.message || 'Save failed. Reload before retrying.'); setReady(false) }
    finally { locked.current = false; setBusy(false) }
  }

  return <section className="project-panel" aria-label="Admin symbol legends">
    <h2>Admin · Symbol legends</h2>
    <p>Register symbol meanings from the supplied drawing legends. Active classes become available in Designer corrections.</p>
    <button type="button" className="btn btn-outline-dark" aria-expanded={open} onClick={() => {setOpen(!open); if (!open) load()}}>Manage symbol legends</button>
    {open && <>
      <p>{records.filter(item => item.is_active).length} active classes. Catalog changes do not train the detector or approve floor-plan geometry.</p>
      <button type="button" className="btn btn-ghost" disabled={busy} onClick={load}>Reload catalog</button>
      <form className="project-floor-create-form" onSubmit={event => {event.preventDefault(); save()}}>
        <label>Class number<input type="number" min="0" max="2147483647" step="1" required value={classId} disabled={busy || !ready} onChange={event => setClassId(event.target.value)} /></label>
        <label>Legend name<input required maxLength={255} value={name} disabled={busy || !ready} onChange={event => setName(event.target.value)} /></label>
        <button className="btn btn-outline-dark" disabled={busy || !ready} type="submit">Add active legend</button>
      </form>
      <p>Use a unique class number. Keep the drawing’s exact meaning; unresolved mappings stay outside the active catalog.</p>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <ul>{records.map(record => <li key={record.id}>{record.class_id} · {record.name} · {record.is_active ? 'active' : 'inactive'} <button type="button" disabled={busy || !ready} onClick={() => save(record)}>{record.is_active ? 'Deactivate' : 'Activate'} {record.name}</button></li>)}</ul>
    </>}
  </section>
}
