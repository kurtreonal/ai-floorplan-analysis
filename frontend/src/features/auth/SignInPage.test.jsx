/* @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { beginOAuthSignIn } from '../../api/auth.js'
import { SignInPage } from './SignInPage.jsx'

vi.mock('../../api/auth.js', () => ({ beginOAuthSignIn: vi.fn() }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function session(status = 'unauthenticated', extra = {}) {
  return {
    status,
    user: status === 'authenticated' ? { display_name: 'VED Designer' } : null,
    signOut: vi.fn(),
    retry: vi.fn(),
    isSigningOut: false,
    error: null,
    ...extra,
  }
}

describe('explicit sign-in and account switching', () => {
  it('does not start OAuth until Sign in is clicked', () => {
    render(<SignInPage session={session()} />)
    expect(beginOAuthSignIn).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(beginOAuthSignIn).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: 'Redirecting…' }).disabled).toBe(true)
  })

  it('does not start sign-in while restoring an existing session', () => {
    render(<SignInPage session={session('loading')} />)
    expect(screen.queryByRole('button', { name: 'Sign in' })).toBeNull()
    expect(beginOAuthSignIn).not.toHaveBeenCalled()
  })

  it('lets an authenticated user switch without automatically starting OAuth', () => {
    const current = session('authenticated')
    render(<SignInPage session={current} />)
    expect(screen.getByRole('link', { name: 'Open workspace' }).getAttribute('href')).toBe('#/app')
    fireEvent.click(screen.getByRole('button', { name: 'Switch account' }))
    expect(current.signOut).toHaveBeenCalledTimes(1)
    expect(beginOAuthSignIn).not.toHaveBeenCalled()
  })

  it('disables switching while sign-out is in progress', () => {
    const current = session('authenticated', { isSigningOut: true })
    render(<SignInPage session={current} />)
    fireEvent.click(screen.getByRole('button', { name: 'Signing out…' }))
    expect(current.signOut).not.toHaveBeenCalled()
  })

  it('shows a failed sign-out and keeps the current account switchable', () => {
    render(<SignInPage session={session('authenticated', {
      error: 'We could not sign you out. Please try again.',
    })} />)
    expect(screen.getByRole('alert').textContent).toContain('We could not sign you out.')
    expect(screen.getByRole('button', { name: 'Switch account' }).disabled).toBe(false)
  })

  it('keeps the explicit retry action on session failure', () => {
    const current = session('error')
    render(<SignInPage session={current} />)
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(current.retry).toHaveBeenCalledTimes(1)
    expect(beginOAuthSignIn).not.toHaveBeenCalled()
  })
})
