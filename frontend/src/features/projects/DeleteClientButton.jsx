import { useState } from 'react'
import { workflowRequest } from '../../api/clientWorkflow.js'
import { Button } from '../../components/ui/button.jsx'
import { AccountDialog } from '../settings/AccountDialog.jsx'

export function DeleteClientButton({ clientId, name, onDeleted }) {
  const [account, setAccount] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function open() {
    setBusy(true); setError('')
    try {
      const accounts = await workflowRequest('/admin/accounts')
      const current = accounts.find(item => item.id === clientId && item.role === 'CLIENT' && !item.disabled)
      if (!current) throw new Error('This client is no longer active. Reload the client list.')
      setAccount(current)
    } catch (failure) { setError(failure.message) }
    finally { setBusy(false) }
  }
  async function remove(event) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      await workflowRequest(`/admin/accounts/${account.id}`, { method: 'DELETE', body: { expected_revision: account.revision } })
      setAccount(null)
      window.dispatchEvent(new Event('ved:accounts-changed'))
      onDeleted?.(clientId)
    } catch (failure) { setError(failure.message) }
    finally { setBusy(false) }
  }
  return <>
    <Button variant="outline" className="workflow-danger" disabled={busy} onClick={open}>Delete client<span className="sr-only"> {name}</span></Button>
    {error && !account && <small role="alert">{error}</small>}
    {account && <AccountDialog title={`Delete ${name}?`} description="Removes this client's sign-in details and profile. Saved projects, layouts and estimates remain in history." busy={busy} onClose={() => setAccount(null)}>
      <form className="account-form" onSubmit={remove}>
        <p className="account-warning">Password and Google sign-in will stop, recovery emails will be removed, and active sessions will end. This cannot restore the old sign-in.</p>
        <label className="account-check"><input type="checkbox" required/>I understand and want to delete this client account.</label>
        {error && <p role="alert">{error}</p>}
        <footer className="account-actions"><Button variant="outline" type="button" disabled={busy} onClick={() => setAccount(null)}>Cancel</Button><Button type="submit" disabled={busy}>{busy ? 'Deleting…' : 'Delete client'}</Button></footer>
      </form>
    </AccountDialog>}
  </>
}
