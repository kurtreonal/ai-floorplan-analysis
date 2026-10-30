// @vitest-environment jsdom
import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {AuthRecoveryScreen} from './AuthRecoveryScreen.jsx'
import {SignInPage} from './SignInPage.jsx'
import {beginOAuthSignIn} from '../../api/auth.js'
vi.mock('../../api/auth.js',()=>({beginOAuthSignIn:vi.fn()}))
afterEach(()=>{cleanup();window.location.hash='';vi.clearAllMocks()})

it('shows a simple focused recovery screen with an actionable retry',()=>{
  const retry=vi.fn()
  render(<AuthRecoveryScreen onRetry={retry} unavailable />)
  expect(screen.getByRole('heading',{name:'Temporarily unavailable'})).toBe(document.activeElement)
  expect(screen.getByRole('alert').textContent).not.toMatch(/SQL|AUTH_|database|detail/)
  fireEvent.click(screen.getByRole('button',{name:'Try again'}))
  expect(retry).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('link',{name:'Return to home'}).getAttribute('href')).toBe('#/')
})

it('disables repeated sign-in attempts while redirecting',()=>{
  const retry=vi.fn()
  render(<AuthRecoveryScreen onRetry={retry} busy />)
  fireEvent.click(screen.getByRole('button',{name:'Connecting…'}))
  expect(retry).not.toHaveBeenCalled()
})

it('turns the callback failure into a deliberate sign-in retry without echoing its data',()=>{
  window.location.hash='#/signin?auth_error=service-unavailable&error=private-technical-details'
  render(<SignInPage session={{status:'unauthenticated'}} />)
  expect(screen.getByRole('heading',{name:'Temporarily unavailable'})).toBeTruthy()
  expect(document.body.textContent).not.toContain('private-technical-details')
  expect(beginOAuthSignIn).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button',{name:'Try again'}))
  expect(beginOAuthSignIn).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('button',{name:'Connecting…'}).disabled).toBe(true)
})

it('keeps session retry separate from starting a fresh OAuth request',()=>{
  const retry=vi.fn()
  render(<SignInPage session={{status:'error',retry,error:'{"detail":"private SQL"}'}} />)
  expect(document.body.textContent).not.toContain('private SQL')
  fireEvent.click(screen.getByRole('button',{name:'Try again'}))
  expect(retry).toHaveBeenCalledOnce()
  expect(beginOAuthSignIn).not.toHaveBeenCalled()
})
