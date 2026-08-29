import { describe, expect, it } from 'vitest'

import { getProtectedRouteRedirect } from './authRoutes.js'
import { getDetectionReviewHref, getProjectHref, parseProjectRoute } from './projectRoutes.js'


describe('project hash routes', () => {
  it('parses the dashboard and positive project IDs', () => {
    expect(parseProjectRoute('/app')).toEqual({ view: 'dashboard', projectId: null })
    expect(parseProjectRoute('/app/projects/42')).toEqual({ view: 'project', projectId: 42 })
    expect(getProjectHref(42)).toBe('#/app/projects/42')
  })

  it('parses and builds an exact detection review route', () => {
    expect(parseProjectRoute('/app/projects/15/floor-plans/81/detections/103')).toEqual({
      view: 'detection-review', projectId: 15, floorPlanId: 81, processingJobId: 103,
    })
    expect(getDetectionReviewHref(15, 81, 103)).toBe(
      '#/app/projects/15/floor-plans/81/detections/103',
    )
  })

  it('rejects malformed detection review segments', () => {
    for (const route of [
      '/app/projects/1/floor-plans/2/detections',
      '/app/projects/1/floor-plans/2/detections/0',
      '/app/projects/1/floor-plans/-2/detections/3',
      '/app/projects/1/floor-plans/2/detections/3/extra',
      '/app/projects/1/floor-plans/2/detections/3.1',
      '/app/projects/1/floor-plans/2/detections/%33',
      '/app/projects/999999999999999999/floor-plans/2/detections/3',
    ]) expect(parseProjectRoute(route)).toEqual({ view: 'invalid', projectId: null })
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
