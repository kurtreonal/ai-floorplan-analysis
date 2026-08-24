import { describe, expect, it } from 'vitest'

import { getProtectedRouteRedirect } from './authRoutes.js'
import { getProjectHref, parseProjectRoute } from './projectRoutes.js'


describe('project hash routes', () => {
  it('parses the dashboard and positive project IDs', () => {
    expect(parseProjectRoute('/app')).toEqual({ view: 'dashboard', projectId: null })
    expect(parseProjectRoute('/app/projects/42')).toEqual({ view: 'project', projectId: 42 })
    expect(getProjectHref(42)).toBe('#/app/projects/42')
  })

  it('rejects missing, invalid, and unsafe project IDs', () => {
    expect(parseProjectRoute('/app/projects')).toEqual({ view: 'invalid', projectId: null })
    expect(parseProjectRoute('/app/projects/0')).toEqual({ view: 'invalid', projectId: null })
    expect(parseProjectRoute('/app/projects/nope')).toEqual({ view: 'invalid', projectId: null })
    expect(parseProjectRoute('/app/projects/999999999999999999999')).toEqual({ view: 'invalid', projectId: null })
  })

  it('keeps unauthenticated application routes redirected to sign-in', () => {
    expect(getProtectedRouteRedirect('unauthenticated')).toBe(
      '#/signin?reason=authentication-required',
    )
    expect(getProtectedRouteRedirect('authenticated')).toBeNull()
  })
})
