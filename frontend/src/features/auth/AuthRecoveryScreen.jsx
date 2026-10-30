import { useEffect, useRef } from 'react'
import { CloudOff, RefreshCw } from 'lucide-react'
import vedLogo from '../../assets/ved-logo.png'
import './authRecovery.css'

export function AuthRecoveryScreen({ onRetry, busy=false, signIn=false, unavailable=false }) {
  const heading=useRef(null)
  useEffect(()=>{heading.current?.focus()},[])
  return <main className="auth-shell auth-recovery-shell">
    <a className="auth-brand" href="#/" aria-label="Return to VED home"><img src={vedLogo} alt="VED Electrical Services" /></a>
    <section className="auth-card auth-recovery-card" role="alert" aria-labelledby="auth-recovery-title">
      <span className="auth-recovery-icon"><CloudOff size={28} aria-hidden="true" /></span>
      <h1 id="auth-recovery-title" ref={heading} tabIndex={-1}>{unavailable ? 'Temporarily unavailable' : signIn ? 'Sign-in didn’t finish' : 'Let’s reconnect'}</h1>
      <p className="auth-intro">{unavailable ? 'VED isn’t ready just yet. Please try again in a moment.' : 'We couldn’t reconnect to your account. Please try again.'}</p>
      <button type="button" className="btn btn-accent auth-primary" onClick={onRetry} disabled={busy}>
        <RefreshCw size={16} aria-hidden="true" />{busy ? 'Connecting…' : 'Try again'}
      </button>
      <a className="auth-home-link" href="#/">Return to home</a>
    </section>
  </main>
}
