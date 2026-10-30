import { useState } from 'react'
import { workflowRequest } from '../../api/clientWorkflow.js'

export function SignInVerification({ channels = [], onComplete, onCancel }) {
  const [channel, setChannel] = useState(channels[0]?.channel || 'primary'), [challenge, setChallenge] = useState(null)
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  async function send() {
    setBusy(true); setError('')
    try { setChallenge(await workflowRequest('/auth/send-code', { method: 'POST', body: { channel } })) }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  async function verify(event) {
    event.preventDefault(); setBusy(true); setError('')
    const data = new FormData(event.currentTarget)
    try { await workflowRequest('/auth/verify-code', { method: 'POST', body: { challenge_id: challenge.challenge_id, code: data.get('code'), remember_device: data.get('remember') === 'on' } }); onComplete() }
    catch (e) { setError(e.message); setBusy(false) }
  }
  return <section><h2>Verify this sign-in</h2><p className="signin-access-note">Use your primary or verified backup email. We ask when signing in, not while you work.</p><div className="signin-password-form"><label>Send code to<select value={channel} onChange={e => { setChannel(e.target.value); setChallenge(null) }}>{channels.map(x => <option key={x.channel} value={x.channel}>{x.channel === 'primary' ? 'Primary' : 'Backup'} · {x.email}</option>)}</select></label><button type="button" className="btn signin-google" disabled={busy} onClick={send}>{busy ? 'Please wait…' : challenge ? 'Request another code' : 'Send 5-digit code'}</button></div>
    {challenge && <form className="signin-password-form" onSubmit={verify}><p className="signin-access-note">Code sent to {challenge.destination}. Expires in five minutes. Wait 60 seconds before requesting another.</p><label>5-digit code<input name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{5}" minLength={5} maxLength={5} required autoFocus/></label><label className="signin-remember"><input name="remember" type="checkbox"/>Trust this device for 30 days</label><button className="btn btn-accent auth-primary" disabled={busy}>Verify &amp; sign in</button></form>}{error && <p role="alert">{error}</p>}<button className="signin-switch" type="button" disabled={busy} onClick={onCancel}>Back to sign-in</button></section>
}

export function PasswordRecovery({ onCancel, onComplete }) {
  const [stage, setStage] = useState('request'), [challenge, setChallenge] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState('')
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('')
    const data = Object.fromEntries(new FormData(event.currentTarget))
    try {
      if (stage === 'request') { setChallenge(await workflowRequest('/auth/recover', { method: 'POST', body: data })); setStage('code') }
      else if (stage === 'code') { await workflowRequest('/auth/verify-code', { method: 'POST', body: { challenge_id: challenge.challenge_id, code: data.code } }); setStage('password') }
      else { if (data.password !== data.confirm) throw new Error('The passwords do not match.'); await workflowRequest('/auth/reset-password', { method: 'POST', body: { password: data.password,confirm_password:data.confirm } }); onComplete() }
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  return <section><h2>Recover your VED account</h2><p className="signin-access-note">Use a previously verified primary or backup email. This changes your VED password, not your Gmail password.</p><form className="signin-password-form" onSubmit={submit} key={stage}>
    {stage === 'request' ? <><label>Verified email address<input name="email" type="email" autoComplete="email" required maxLength={254} placeholder="Your verified Gmail or backup email"/></label><p className="signin-access-note">A verified email is required. If you cannot access either address, contact VED Admin.</p></> : stage === 'code' ? <><p className="signin-access-note">If this email is verified for one active account, a code has been sent. It expires in five minutes. If no code arrives, try your verified backup email or contact Admin.</p><label>5-digit code<input name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{5}" minLength={5} maxLength={5} required/></label><button className="signin-switch" type="button" onClick={() => setStage('request')}>Use a different email / request again</button></> : <><label>New VED password<input name="password" type="password" autoComplete="new-password" required minLength={15} maxLength={256}/></label><label>Confirm password<input name="confirm" type="password" autoComplete="new-password" required minLength={15} maxLength={256}/></label></>}
    {error && <p role="alert">{error}</p>}<button className="btn btn-accent auth-primary" disabled={busy}>{busy ? 'Please wait…' : stage === 'request' ? 'Request code' : stage === 'code' ? 'Verify code' : 'Reset VED password'}</button><button className="signin-switch" type="button" onClick={onCancel} disabled={busy}>Back to sign-in</button>
  </form></section>
}
