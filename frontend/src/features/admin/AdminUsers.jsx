import { useEffect, useState } from 'react'
import { Plus, Search, Users } from 'lucide-react'
import { workflowRequest } from '../../api/clientWorkflow.js'
import { Button } from '../../components/ui/button.jsx'
import { AccountDialog } from '../settings/AccountDialog.jsx'
import { PersonFields } from './PersonFields.jsx'

export function AdminUsers({ onChanged }) {
  const [accounts, setAccounts] = useState([]), [error, setError] = useState(''), [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false), [notice, setNotice] = useState(''), [search, setSearch] = useState('')
  const [editor, setEditor] = useState(null), [removing, setRemoving] = useState(null), [formError, setFormError] = useState('')
  const [page, setPage] = useState(0), [roleFilter, setRoleFilter] = useState('all')
  useEffect(() => {
    const c = new AbortController()
    const refresh=()=>workflowRequest('/admin/accounts', { signal: c.signal }).then(setAccounts).catch(e => { if (e.name !== 'AbortError') setError(e.message) }).finally(() => { if (!c.signal.aborted) setLoading(false) })
    refresh();window.addEventListener('ved:accounts-changed',refresh)
    return () => {c.abort();window.removeEventListener('ved:accounts-changed',refresh)}
  }, [])
  function changed(account) {
    setAccounts(current => [...current.filter(x => x.id !== account.id), ...(account.disabled ? [] : [account])].sort((a, b) => a.label.localeCompare(b.label)))
    window.dispatchEvent(new Event('ved:accounts-changed')); onChanged?.()
  }
  async function save(event) {
    event.preventDefault(); setBusy(true); setFormError(''); setNotice('')
    const data = Object.fromEntries(new FormData(event.currentTarget))
    if((data.password || data.confirm_password) && data.password!==data.confirm_password){setFormError('The passwords do not match.');setBusy(false);return}
    const body = { first_name:data.first_name,last_name:data.last_name,middle_name:data.middle_name || null,phone_number:data.phone_number,location:data.location,email: data.email || null, role: data.role, username: data.username || null,
      ...(data.password ? { password: data.password,confirm_password:data.confirm_password } : {}),
      ...(editor.id ? { disabled: data.disabled === 'on', expected_revision: editor.revision } : {}) }
    try {
      const account = await workflowRequest(`/admin/accounts${editor.id ? `/${editor.id}` : ''}`, { method: editor.id ? 'PUT' : 'POST', body })
      changed(account); setEditor(null)
      setNotice(editor.id ? 'Account updated. Previous sessions have been signed out.' : 'Account created. Share the credentials privately. The user can connect Google after signing in.')
    } catch (e) { setFormError(e.message) } finally { setBusy(false) }
  }
  async function remove(event) {
    event.preventDefault(); setBusy(true); setFormError('')
    try {
      const account = await workflowRequest(`/admin/accounts/${removing.id}`, { method: 'DELETE', body: { expected_revision: removing.revision } })
      changed(account); setRemoving(null); setNotice('User removed from the active list. The action is recorded in Admin activity; saved work is preserved.')
    } catch (e) { setFormError(e.message) } finally { setBusy(false) }
  }
  const filtered = accounts.filter(x => (roleFilter === 'all' || x.role === roleFilter) && `${x.label} ${x.username || ''} ${x.email || ''} ${x.role}`.toLowerCase().includes(search.toLowerCase()))
  const pageCount = Math.max(1, Math.ceil(filtered.length / 10)), currentPage = Math.min(page, pageCount - 1)
  return <section className="workflow-panel account-management" aria-labelledby="managed-users-title">
    <header className="account-section-heading"><div><h2 id="managed-users-title"><Users size={20} aria-hidden="true"/> Users</h2><p>Admin-managed access for Designers and Clients. Google never creates an account.</p></div><Button onClick={() => { setFormError(''); setEditor({ role: 'DESIGNER' }) }}><Plus size={16}/>Add user</Button></header>
    <div className="account-list-controls"><label className="account-search"><Search size={17} aria-hidden="true"/><input aria-label="Search users" placeholder="Search name, username or email" value={search} onChange={e => { setSearch(e.target.value); setPage(0) }}/></label><label>Role<select aria-label="Filter users by role" value={roleFilter} onChange={e => { setRoleFilter(e.target.value); setPage(0) }}><option value="all">All roles</option><option value="DESIGNER">Designers</option><option value="CLIENT">Clients</option><option value="ADMIN">Admins</option></select></label></div>
    {loading && <p role="status">Loading users…</p>}{error && <p role="alert">{error}</p>}{notice && <p className="account-notice" role="status">{notice}</p>}
    <div className="studio-table-scroll"><table className="studio-project-table"><caption className="sr-only">User accounts and access management</caption><thead><tr><th>User</th><th>Role</th><th>Sign-in</th><th>Access</th><th>Actions</th></tr></thead><tbody>
      {filtered.slice(currentPage * 10, currentPage * 10 + 10).map(x => <tr key={x.id}><th scope="row">{x.label}<small className="account-secondary">{x.email || `Account #${x.id}`}</small></th><td>{x.role === 'ADMIN' ? 'Admin' : x.role === 'DESIGNER' ? 'Designer' : 'Client'}</td><td>{x.username || 'Password not configured'}<small className="account-secondary">{x.google_linked ? 'Google connected' : 'Google not connected'}</small></td><td><span className={`account-badge${x.disabled || (!x.username && x.role !== 'ADMIN') ? ' account-badge-muted' : ''}`}>{x.disabled ? 'Access removed' : !x.username && x.role !== 'ADMIN' ? 'Needs setup' : 'Active'}</span><small className="account-secondary">{x.assigned_projects} active projects</small></td><td><div className="account-actions"><Button variant="outline" disabled={x.role === 'ADMIN'} onClick={() => { setFormError(''); setEditor(x) }}>Edit<span className="sr-only"> {x.label}</span></Button><Button variant="outline" disabled={x.role === 'ADMIN' || x.disabled} onClick={() => { setFormError(''); setRemoving(x) }}>Delete<span className="sr-only"> {x.label}</span></Button></div>{x.role === 'ADMIN' && <small className="account-secondary">Protected administrator</small>}</td></tr>)}
    </tbody></table></div>{!loading && !filtered.length && <p>No users match your search.</p>}
    {!loading && filtered.length > 0 && <nav className="account-pagination" aria-label="User list pages"><span>{filtered.length} users · Page {currentPage + 1} of {pageCount}</span><Button variant="outline" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>Previous</Button><Button variant="outline" disabled={currentPage + 1 >= pageCount} onClick={() => setPage(currentPage + 1)}>Next</Button></nav>}
    {editor && <AccountDialog title={editor.id ? `Edit ${editor.label}` : 'Add a user'} description={editor.id ? 'Changes affect access immediately. Role changes require reassigning active projects first.' : 'Choose a role and provide the initial username and password.'} busy={busy} onClose={() => setEditor(null)}>
      <form className="account-form" onSubmit={save}>
        {editor.id && <p className="account-warning">Saving signs out this user’s current sessions. Their project history is preserved.</p>}
        <PersonFields person={editor}/><label>Role<select name="role" defaultValue={editor.role}><option value="DESIGNER">Designer</option><option value="CLIENT">Client</option></select></label>
        <label>Contact email <span className="account-secondary">Optional · not automatically verified or linked</span><input name="email" type="email" defaultValue={editor.email || ''} maxLength={320}/></label>
        <label>Username<input name="username" defaultValue={editor.username || ''} required minLength={3} maxLength={80} pattern="[A-Za-z0-9._@+\-]+" autoComplete="off"/></label>
        <label>{editor.id && editor.username ? 'Reset password (optional)' : 'Initial password'}<input name="password" type="password" required={!editor.id || !editor.username} minLength={15} maxLength={256} autoComplete="new-password"/><small>At least 15 characters. Share privately, never in project notes.</small></label>
        <label>Confirm password<input name="confirm_password" type="password" required={!editor.id || !editor.username} minLength={15} maxLength={256} autoComplete="new-password"/><small>Leave both password fields empty to keep the current password.</small></label>
        {editor.id && <><label className="account-check"><input name="disabled" type="checkbox" defaultChecked={editor.disabled}/>Remove sign-in access</label><label className="account-check"><input type="checkbox" required/>I understand these changes affect this user’s access.</label></>}
        {formError && <p role="alert">{formError}</p>}<footer className="account-actions"><Button type="button" variant="outline" disabled={busy} onClick={() => setEditor(null)}>Cancel</Button><Button type="submit" disabled={busy}>{busy ? 'Saving…' : editor.id ? 'Confirm changes' : 'Create account'}</Button></footer>
      </form>
    </AccountDialog>}
    {removing && <AccountDialog title={`Delete ${removing.label}?`} description="Deletes the profile, password, Google links and recovery emails. This cannot restore the old sign-in. Saved projects and authorship IDs remain in history." busy={busy} onClose={() => setRemoving(null)}><form className="account-form" onSubmit={remove}>
      <p className="account-warning">Both password and Google sign-in will stop, and existing sessions will end. {removing.assigned_projects > 0 ? `This user has ${removing.assigned_projects} active projects. Reassign them if another person needs access.` : 'No active projects are assigned.'} Saved work will not be deleted.</p>
      <label className="account-check"><input type="checkbox" required/>I understand and want to remove this user’s access.</label>{formError && <p role="alert">{formError}</p>}<footer className="account-actions"><Button variant="outline" type="button" disabled={busy} onClick={() => setRemoving(null)}>Cancel</Button><Button type="submit" disabled={busy}>{busy ? 'Removing…' : 'Delete user access'}</Button></footer>
    </form></AccountDialog>}
  </section>
}
