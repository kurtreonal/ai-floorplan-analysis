import { useEffect, useState } from 'react'
import { workflowRequest } from '../../api/clientWorkflow.js'
import { Button } from '../../components/ui/button.jsx'
import { PersonFields } from './PersonFields.jsx'
import { DeleteClientButton } from '../projects/DeleteClientButton.jsx'

export function AdminClients({ onChanged }) {
  const [accounts, setAccounts] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  useEffect(() => { const controller = new AbortController()
    workflowRequest('/admin/accounts', { signal: controller.signal }).then(setAccounts).catch(e => { if (e.name !== 'AbortError') setError(e.message) })
    return () => controller.abort()
  }, [])
  async function create(event) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    const form = event.currentTarget, data = Object.fromEntries(new FormData(form))
    if(data.password!==data.confirm_password){setError('The passwords do not match.');setBusy(false);return}
    try {
      const account = await workflowRequest('/admin/clients', { method: 'POST', body: { ...data, email: data.email || null } })
      setAccounts(current => [...current, account]); form.reset(); onChanged?.()
      setNotice(`Client account created for ${account.display_name}. Share the username and password with the client directly.`)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  return <section className="workflow-panel"><h2>Client accounts</h2><p>Create the client’s account, then associate it with a project.</p>
    <form className="workflow-grid" onSubmit={create}>
      <PersonFields/>
      <label className="studio-field">Email (optional)<input name="email" type="email" maxLength={320}/></label>
      <label className="studio-field">Username<input name="username" autoComplete="off" required minLength={3} maxLength={80} pattern="[A-Za-z0-9._@+\-]+"/></label>
      <label className="studio-field">Password<input name="password" type="password" autoComplete="new-password" required minLength={15} maxLength={256}/><small>At least 15 characters. A memorable phrase works well.</small></label>
      <label className="studio-field">Confirm password<input name="confirm_password" type="password" autoComplete="new-password" required minLength={15} maxLength={256}/></label>
      <Button disabled={busy} type="submit">{busy ? 'Creating…' : 'Create client account'}</Button>
    </form>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <div className="studio-table-scroll"><table className="studio-project-table"><thead><tr><th>Client</th><th>Username</th><th>Email</th><th>Delete</th></tr></thead><tbody>
      {accounts.filter(x => x.role === 'CLIENT' && !x.disabled).map(x => <tr key={x.id}><th scope="row">{x.display_name}</th><td>{x.username}</td><td>{x.email || '—'}</td><td><DeleteClientButton clientId={x.id} name={x.label} onDeleted={id=>{setAccounts(current=>current.filter(a=>a.id!==id));onChanged?.()}}/></td></tr>)}
    </tbody></table></div>
  </section>
}
