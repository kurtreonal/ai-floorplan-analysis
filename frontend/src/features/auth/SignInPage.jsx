import { useEffect, useState } from 'react'
import { SignInVerification, PasswordRecovery } from './SignInVerification.jsx'
import { ArrowLeft, ArrowRight, ShieldCheck, UserRound } from 'lucide-react'

import { beginOAuthSignIn } from '../../api/auth.js'
import vedLogo from '../../assets/ved-logo.png'
import './signIn.css'
import { workflowRequest } from '../../api/clientWorkflow.js'

function hasAuthenticationError() {
  const query = window.location.hash.split('?')[1]
  if (!query) {
    return false
  }

  const parameters = new URLSearchParams(query)
  return parameters.has('auth_error') || parameters.has('error')
}

export function SignInPage({ session }) {
  const [isSigningIn, setIsSigningIn] = useState(false)
  const [loginError, setLoginError] = useState('')
  const [pending, setPending] = useState(null), [recovering, setRecovering] = useState(false), [notice, setNotice] = useState('')
  useEffect(() => {
    if (!window.location.hash.includes('verify=required')) return
    workflowRequest('/auth/pending').then(setPending).catch(e => setLoginError(e.message))
  }, [])
  function complete() { session.retry(); window.location.replace('#/app') }
  async function passwordSignIn(event) {
    event.preventDefault(); setIsSigningIn(true); setLoginError('')
    try {
      const result = await workflowRequest('/auth/password-login', { method: 'POST', body: Object.fromEntries(new FormData(event.currentTarget)) })
      if (result.verification_required) { setPending(result); setIsSigningIn(false) } else complete()
    } catch (error) { setLoginError(error.message); setIsSigningIn(false) }
  }
  const callbackError = hasAuthenticationError()
  const authReason = new URLSearchParams(window.location.hash.split('?')[1] || '').get('auth_error')

  function startSignIn() {
    setIsSigningIn(true)
    beginOAuthSignIn()
  }

  const isAuthenticated = session.status === 'authenticated'
  const hasError = callbackError || session.status === 'error' || Boolean(session.error)

  return (
    <main className="auth-shell auth-signin-shell">
      <a className="auth-brand" href="#/" aria-label="Return to VED home">
        <img src={vedLogo} alt="VED Electrical Services" />
        <span aria-hidden="true">VED <span>Electrical Services</span></span>
      </a>

      <section className="auth-card auth-signin-card" aria-labelledby="sign-in-title">
        <h1 id="sign-in-title">
          {isAuthenticated ? 'Welcome back' : 'Sign in to VED'}
        </h1>
        <p className="auth-intro">
          {isAuthenticated
            ? 'Pick up where you left off.'
            : 'Use the account provided by your administrator.'}
        </p>

        {hasError && (
          <div className="auth-message auth-message-error" role="alert">
            {authReason === 'account-not-provisioned' ? 'This Google account is not connected to an enabled VED account. Sign in with your Admin-provided username and password, then connect Google in User settings.' : session.status === 'error' ? 'The sign-in service is temporarily unavailable. Try again in a moment.' : 'Google sign-in did not finish. You can retry or use your username and password.'}
          </div>
        )}

        {session.status === 'loading' && (
          <div className="auth-message" role="status">
            <span className="auth-spinner" aria-hidden="true" />
            Checking your session…
          </div>
        )}

        {notice && <p role="status">{notice}</p>}
        {pending ? <SignInVerification channels={pending.channels} onComplete={complete} onCancel={() => { setPending(null); setIsSigningIn(false) }}/>
          : recovering ? <PasswordRecovery onCancel={() => setRecovering(false)} onComplete={() => { setRecovering(false); setNotice('VED password reset. Sign in with your new password.'); setIsSigningIn(false) }}/>
          : isAuthenticated ? (
          <>
            <div className="signin-account">
              <span className="signin-account-icon"><UserRound size={20} aria-hidden="true" /></span>
              <div className="signin-account-identity">
                <span>Signed in as</span>
                <strong>{session.user.display_name || session.user.email || 'a VED user'}</strong>
              </div>
              <button
                className="signin-switch"
                type="button"
                disabled={session.isSigningOut}
                onClick={session.signOut}
              >
                {session.isSigningOut ? 'Signing out…' : 'Switch account'}
              </button>
            </div>
            <a className="btn btn-accent auth-primary" href="#/app">
              Open workspace <ArrowRight size={18} aria-hidden="true" />
            </a>
          </>
        ) : (
          session.status !== 'loading' && (
            <div>
            <form className="signin-password-form" onSubmit={passwordSignIn}>
              <label className="studio-field">Username<input name="username" required autoComplete="username" minLength={3} maxLength={80} autoCapitalize="none" spellCheck={false}/></label>
              <label className="studio-field">Password<input name="password" type="password" required autoComplete="current-password" maxLength={256}/></label>
              <button className="signin-switch" type="button" onClick={() => { setRecovering(true); setLoginError('') }}>Forgot your VED password?</button>
              {loginError && <p role="alert">{loginError}</p>}
              <button className="btn btn-accent auth-primary" type="submit" disabled={isSigningIn}>{isSigningIn ? 'Signing in…' : 'Sign in'}</button>
            </form>
            <div className="signin-method-divider"><span>or</span></div>
            <button
              className="btn signin-google"
              type="button"
              disabled={isSigningIn}
              onClick={startSignIn}
            >
              {isSigningIn ? 'Connecting…' : 'Sign in with Google'}
              {!isSigningIn && <ArrowRight size={18} aria-hidden="true" />}
            </button>
            <p className="signin-access-note">Google works after you connect it in User settings.<br/>Need an account or a password reset? Contact your Admin.</p>
            </div>
          )
        )}

        <footer className="signin-footer">
          <a className="auth-home-link" href="#/"><ArrowLeft size={14} aria-hidden="true" /> Back to home</a>
          <span><ShieldCheck size={14} aria-hidden="true" /> Secure sign-in</span>
        </footer>
      </section>
    </main>
  )
}
