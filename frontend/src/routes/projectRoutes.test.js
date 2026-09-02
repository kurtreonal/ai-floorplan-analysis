import { describe, expect, it } from 'vitest'

import { getProtectedRouteRedirect } from './authRoutes.js'
import {
  getDetectionReviewHref, getLayoutHref, getProjectHref, getViewer3dHref, parseProjectRoute,
} from './projectRoutes.js'


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

  it('parses and builds the exact current layout route', () => {
    expect(parseProjectRoute('/app/projects/15/floors/2/layout')).toEqual({
      view: 'layout', projectId: 15, projectFloorId: 2,
    })
    expect(getLayoutHref(15, 2)).toBe('#/app/projects/15/floors/2/layout')
    for (const route of [
      '/app/projects/15/floors/0/layout', '/app/projects/15/floors/-2/layout',
      '/app/projects/15/floors/2.1/layout', '/app/projects/15/floors/%32/layout',
      '/app/projects/15/floors/2/layout/extra',
      '/app/projects/999999999999999999/floors/2/layout',
    ]) expect(parseProjectRoute(route)).toEqual({ view: 'invalid', projectId: null })
    for (const ids of [[0, 2], [15, -2], [15, 2.1], [15, Number.MAX_SAFE_INTEGER + 1]]) {
      expect(() => getLayoutHref(...ids)).toThrow()
    }
  })

  it('parses and builds the exact 3D viewer route', () => {
    expect(parseProjectRoute('/app/projects/15/floors/2/viewer-3d')).toEqual({
      view: 'viewer-3d', projectId: 15, projectFloorId: 2,
    })
    expect(getViewer3dHref(15, 2)).toBe('#/app/projects/15/floors/2/viewer-3d')
    for (const route of [
      '/app/projects/15/floors/0/viewer-3d', '/app/projects/15/floors/-2/viewer-3d',
      '/app/projects/15/floors/2.1/viewer-3d', '/app/projects/15/floors/%32/viewer-3d',
      '/app/projects/15/floors/2/viewer-3d/extra',
      '/app/projects/999999999999999999/floors/2/viewer-3d',
    ]) expect(parseProjectRoute(route)).toEqual({ view: 'invalid', projectId: null })
    for (const ids of [[0, 2], [15, -2], [15, 2.1], [15, Number.MAX_SAFE_INTEGER + 1]]) {
      expect(() => getViewer3dHref(...ids)).toThrow()
    }
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
