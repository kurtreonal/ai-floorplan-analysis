import { useEffect, useState } from 'react'
import { Mail } from 'lucide-react'
import { workflowRequest } from '../../api/clientWorkflow.js'
import { Button } from '../../components/ui/button.jsx'
import { AccountDialog } from './AccountDialog.jsx'
import { notify } from '../../components/notifications.js'

export function EmailAuthenticationRow({ username }) {
  const [record, setRecord] = useState(null), [open, setOpen] = useState(false), [challenge, setChallenge] = useState(null)
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [checking, setChecking] = useState(false)
  useEffect(() => { const c = new AbortController(); workflowRequest('/auth/emails', { signal: c.signal }).then(setRecord).catch(e => { if (e.name !== 'AbortError') setError(e.message) }); return () => c.abort() }, [])
  async function refreshDelivery() {
    setChecking(true); setError('')
    try { setRecord(await workflowRequest('/auth/emails')) }
    catch (e) { setError(e.message) } finally { setChecking(false) }
  }
  async function enroll(event) {
    event.preventDefault(); setBusy(true); setError('')
    const data = Object.fromEntries(new FormData(event.currentTarget))
    try { setChallenge(await workflowRequest('/auth/emails', { method: 'POST', body: { ...data, current_password: data.current_password || null } })) }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  async function verify(event) {
    event.preventDefault(); setBusy(true); setError('')
    const code = new FormData(event.currentTarget).get('code')
    try {
      await workflowRequest('/auth/verify-code', { method: 'POST', body: { challenge_id: challenge.challenge_id, code } })
      setRecord(await workflowRequest('/auth/emails')); setChallenge(null); notify('Email verified. Sign-in and recovery codes can use this address.')
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const primary = record?.addresses.find(x => x.primary), backup = record?.addresses.find(x => !x.primary)
  return <><div className="account-method-row"><Mail size={22} aria-hidden="true"/><div><strong>Email &amp; recovery</strong><p>{primary?.email || 'Primary email not verified'}</p><small className="account-secondary">{backup ? `Backup: ${backup.email}` : 'Add a verified backup email'} · {record?.verification_enabled ? 'Sign-in verification enabled' : 'Email verification not enabled'}</small></div><Button variant="outline" onClick={() => { setOpen(true); refreshDelivery() }}>Manage emails</Button></div>
    {open && <AccountDialog title={challenge ? 'Verify your email' : 'Email & recovery'} description={challenge ? `Enter the five-digit code sent to ${challenge.destination}. It expires in five minutes.` : 'Verified emails receive sign-in codes and can reset your VED password. This does not reset your Google password.'} busy={busy} onClose={() => { setOpen(false); setChallenge(null); setError('') }}>
      {checking && <p role="status">Checking email delivery…</p>}
      {!checking && record && !record.delivery_available && <div className="account-warning"><p>Email delivery needs Admin setup. Existing password and Google sign-in remain available.</p><Button type="button" variant="outline" disabled={busy} onClick={refreshDelivery}>Refresh delivery status</Button></div>}
      {challenge ? <form className="account-form" onSubmit={verify}><label>5-digit code<input name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{5}" minLength={5} maxLength={5} required autoFocus/></label>{error && <p role="alert">{error}</p>}<footer className="account-actions"><Button variant="outline" type="button" disabled={busy} onClick={() => setChallenge(null)}>Change email / request again</Button><Button type="submit" disabled={busy}>{busy ? 'Verifying…' : 'Verify email'}</Button></footer></form> : <>
        <div className="account-email-list">{record?.addresses.map(x => <div key={x.email}><strong>{x.primary ? 'Primary' : 'Backup'}</strong><span>{x.email}</span><small>Verified</small></div>)}{!record?.addresses.length && <p>No verified addresses yet.</p>}</div>
        <form className="account-form" onSubmit={enroll}><label>Email type<select name="channel"><option value="primary">Primary email</option><option value="backup">Backup email</option></select></label><label>Email address<input name="email" type="email" autoComplete="email" required maxLength={254} defaultValue={!primary ? record?.contact_email || '' : ''}/></label>{username && <label>Current VED password<input name="current_password" type="password" required autoComplete="current-password"/></label>}<small>A replacement becomes active only after verification. Sign-in codes are requested at sign-in, not while editing plans.</small>{error && <p role="alert">{error}</p>}<footer className="account-actions"><Button variant="outline" type="button" onClick={() => setOpen(false)} disabled={busy}>Close</Button><Button type="submit" disabled={busy || checking || !record?.delivery_available}>{busy ? 'Sending…' : 'Send verification code'}</Button></footer></form>
      </>}
    </AccountDialog>}
  </>
}
