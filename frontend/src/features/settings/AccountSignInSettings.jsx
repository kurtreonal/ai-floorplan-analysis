import { useEffect, useState } from 'react'
import { workflowRequest } from '../../api/clientWorkflow.js'
import { beginOAuthSignIn } from '../../api/auth.js'
import { Button } from '../../components/ui/button.jsx'
import { KeyRound, Link2 } from 'lucide-react'
import { AccountDialog } from './AccountDialog.jsx'
import { EmailAuthenticationRow } from './EmailAuthenticationRow.jsx'

export function AccountSignInSettings() {
  const [methods, setMethods] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false), [notice, setNotice] = useState('')
  const [editing, setEditing] = useState(null)
  useEffect(() => { const c = new AbortController(); workflowRequest('/auth/methods', { signal: c.signal }).then(setMethods).catch(e => { if (e.name !== 'AbortError') setError(e.message) }); return () => c.abort() }, [])
  async function save(event) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    const form = event.currentTarget, body = Object.fromEntries(new FormData(form))
    if(body.password!==body.confirm_password){setError('The passwords do not match.');setBusy(false);return}
    try { await workflowRequest('/auth/credentials', { method: 'PUT', body: { ...body, current_password: body.current_password || null } });
      setMethods(current => ({ ...current, username: body.username })); setEditing(null); setNotice('Username and password saved. Your other sessions have been signed out.')
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  async function link(event) {
    event.preventDefault(); setBusy(true); setError('')
    const data = new FormData(event.currentTarget)
    try { await workflowRequest('/auth/link-google', { method: 'POST', body: { current_password: data.get('current_password') || null } }); beginOAuthSignIn() }
    catch (e) { setError(e.message); setBusy(false) }
  }
  async function manage(event) {
    event.preventDefault(); setBusy(true); setError('')
    const values = Object.fromEntries(new FormData(event.currentTarget))
    try {
      if (editing === 'email') {
        await workflowRequest('/auth/contact-email', { method: 'PUT', body: { email: values.email || null, current_password: values.current_password || null } })
        setMethods(current => ({ ...current, email: values.email || null })); setNotice('Contact email saved. This does not verify it or link a Google account.')
      } else {
        await workflowRequest('/auth/link-google', { method: 'DELETE', body: { current_password: values.current_password || null } })
        setMethods(current => ({ ...current, google_linked: false })); setNotice('Google disconnected. Continue signing in with your username and password.')
      }
      setEditing(null)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  function open(value) { setError(''); setNotice(''); setEditing(value) }
  return <section className="account-methods" aria-labelledby="signin-methods-title"><h2 id="signin-methods-title">Sign-in methods</h2>
    <p>Your Admin-managed account. Use your password or connect Google as another way to sign in.</p>
    {!methods && !error && <p role="status">Loading sign-in methods…</p>}
    {methods && <div className="account-method-list">
      <EmailAuthenticationRow username={methods.username}/>
      <div className="account-method-row"><KeyRound size={22} aria-hidden="true"/><div><strong>Username &amp; password</strong><p>{methods.username ? `Configured · ${methods.username}` : 'Not configured'}</p></div><Button variant="outline" onClick={() => open('password')}>{methods.username ? 'Change password' : 'Set password'}</Button></div>
      <div className="account-method-row"><Link2 size={22} aria-hidden="true"/><div><strong>Google</strong><p>{methods.google_linked ? 'Connected to your VED account' : 'Not connected'}</p></div><Button variant="outline" onClick={() => open('google')}>{methods.google_linked ? 'Manage Google' : 'Connect Google'}</Button></div>
    </div>}
    {notice && <p className="account-notice" role="status">{notice}</p>}{error && !editing && <p role="alert">{error}</p>}
    {editing && <AccountDialog busy={busy} onClose={() => setEditing(null)} title={editing === 'password' ? 'Username & password' : editing === 'email' ? 'Contact email' : methods.google_linked ? 'Connected Google account' : 'Connect Google'} description={editing === 'password' ? 'Use a memorable phrase with at least 15 characters. Saving ends your other sessions.' : editing === 'email' ? 'Changing this address does not verify it or change your Google sign-in identity.' : methods.google_linked ? 'You can disconnect Google without deleting your VED account or projects.' : 'Confirm your password, then choose your Google account in the secure Google window.'}>
      <form className="account-form" onSubmit={editing === 'password' ? save : editing === 'google' && !methods.google_linked ? link : manage}>
        {editing === 'password' && <label>Username<input name="username" defaultValue={methods.username || ''} required minLength={3} maxLength={80} pattern="[A-Za-z0-9._@+\-]+" autoComplete="username"/></label>}
        {editing === 'email' && <label>Email address<input name="email" type="email" maxLength={320} defaultValue={methods.email || ''} autoComplete="email"/></label>}
        {methods.username && <label>Current password<input name="current_password" type="password" required autoComplete="current-password"/></label>}
        {editing === 'password' && <label>New password<input name="password" type="password" autoComplete="new-password" required minLength={15} maxLength={256}/><small>At least 15 characters.</small></label>}
        {editing === 'password' && <label>Confirm new password<input name="confirm_password" type="password" autoComplete="new-password" required minLength={15} maxLength={256}/></label>}
        {editing === 'google' && methods.google_linked && <p className="account-warning">{methods.username ? 'Disconnecting removes Google sign-in and signs out other sessions. Your password will still work.' : 'Set a username and password first so you do not lose access.'}</p>}
        {error && <p role="alert">{error}</p>}<footer className="account-actions"><Button variant="outline" type="button" onClick={() => setEditing(null)} disabled={busy}>Cancel</Button><Button type="submit" disabled={busy || (editing === 'google' && methods.google_linked && !methods.username)}>{busy ? 'Please wait…' : editing === 'password' ? 'Save password' : editing === 'email' ? 'Save email' : methods.google_linked ? 'Disconnect Google' : 'Continue to Google'}</Button></footer>
      </form>
    </AccountDialog>}
  </section>
}
