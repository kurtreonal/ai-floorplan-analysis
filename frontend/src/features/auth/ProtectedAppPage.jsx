import { useEffect } from 'react'

import vedLogo from '../../assets/ved-logo.png'
import { getProtectedRouteRedirect } from '../../routes/authRoutes.js'

export function ProtectedAppPage({ session }) {
  useEffect(() => {
    const redirect = getProtectedRouteRedirect(session.status)
    if (redirect) {
      window.location.replace(redirect)
    }
  }, [session.status])

  if (session.status === 'loading' || session.status === 'unauthenticated') {
    return (
      <main className="auth-shell">
        <div className="auth-message auth-route-status" role="status">
          <span className="auth-spinner" aria-hidden="true" />
          Verifying application access…
        </div>
      </main>
    )
  }

  if (session.status === 'error') {
    return (
      <main className="auth-shell">
        <section className="auth-card" aria-labelledby="access-error-title">
          <div className="auth-card-accent mono">APPLICATION ACCESS</div>
          <h1 id="access-error-title">We couldn’t verify your session.</h1>
          <p className="auth-intro">The authentication service may be temporarily unavailable.</p>
          <button className="btn btn-accent auth-primary" type="button" onClick={session.retry}>
            Try again
          </button>
          <a className="auth-home-link" href="#/">← Return to home</a>
        </section>
      </main>
    )
  }

  return (
    <main className="auth-shell">
      <section className="auth-card auth-card-wide" aria-labelledby="workspace-title">
        <img className="auth-workspace-logo" src={vedLogo} alt="VED Electrical Services" />
        <div className="auth-card-accent mono">AUTHENTICATED APPLICATION</div>
        <h1 id="workspace-title">Your access is confirmed.</h1>
        <p className="auth-intro">
          Welcome, {session.user.display_name || session.user.email || 'VED user'}.
        </p>
        <dl className="auth-profile">
          <div>
            <dt>Role</dt>
            <dd>{session.user.role}</dd>
          </div>
          {session.user.email && (
            <div>
              <dt>Email</dt>
              <dd>{session.user.email}</dd>
            </div>
          )}
        </dl>
        <p className="auth-note">Project workspace features will appear here as their tickets are completed.</p>
        {session.error && (
          <div className="auth-message auth-message-error auth-sign-out-error" role="alert">
            {session.error}
          </div>
        )}
        <button
          className="btn btn-outline-dark auth-sign-out"
          type="button"
          disabled={session.isSigningOut}
          onClick={session.signOut}
        >
          {session.isSigningOut ? 'Signing out…' : 'Sign out'}
        </button>
        <a className="auth-home-link" href="#/">← Return to landing page</a>
      </section>
    </main>
  )
}
