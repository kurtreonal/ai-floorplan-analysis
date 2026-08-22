import { useState } from 'react'

import { beginOAuthSignIn } from '../../api/auth.js'
import vedLogo from '../../assets/ved-logo.png'


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
  const callbackError = hasAuthenticationError()

  function startSignIn() {
    setIsSigningIn(true)
    beginOAuthSignIn()
  }

  const isAuthenticated = session.status === 'authenticated'
  const hasError = callbackError || session.status === 'error'

  return (
    <main className="auth-shell">
      <a className="auth-brand" href="#/" aria-label="Return to VED home">
        <img src={vedLogo} alt="VED Electrical Services" />
      </a>

      <section className="auth-card" aria-labelledby="sign-in-title">
        <div className="auth-card-accent mono">SECURE APPLICATION ACCESS</div>
        <h1 id="sign-in-title">
          {isAuthenticated ? 'Welcome back.' : 'Continue to VED.'}
        </h1>
        <p className="auth-intro">
          {isAuthenticated
            ? `Signed in as ${session.user.display_name || session.user.email || 'a VED user'}.`
            : 'Use your organization account to access electrical planning and estimation tools.'}
        </p>

        {hasError && (
          <div className="auth-message auth-message-error" role="alert">
            Unable to verify your sign-in. Please try again.
          </div>
        )}

        {session.status === 'loading' && (
          <div className="auth-message" role="status">
            <span className="auth-spinner" aria-hidden="true" />
            Checking your session…
          </div>
        )}

        {session.status === 'error' && (
          <button className="btn btn-outline-dark auth-secondary" type="button" onClick={session.retry}>
            Try again
          </button>
        )}

        {isAuthenticated ? (
          <a className="btn btn-accent auth-primary" href="#/app">
            Continue to application
          </a>
        ) : (
          session.status !== 'loading' && (
            <button
              className="btn btn-accent auth-primary"
              type="button"
              disabled={isSigningIn}
              onClick={startSignIn}
            >
              {isSigningIn ? 'Redirecting…' : 'Sign in'}
            </button>
          )
        )}

        <p className="auth-note">
          Authentication is handled securely by your configured account provider. VED never asks for or stores your provider password.
        </p>
        <a className="auth-home-link" href="#/">← Return to home</a>
      </section>
    </main>
  )
}
