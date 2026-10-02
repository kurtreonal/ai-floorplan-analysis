/* @vitest-environment jsdom */
import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { routingRequest } from '../../api/routing.js'
import { useSavedRoute } from './useSavedRoute.js'

vi.mock('../../api/routing.js', () => ({ routingRequest: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks() })

it.each([null, { version_number: 1 }])('preserves a newly saved route against a late response: %s', async (late) => {
  let resolve
  routingRequest.mockImplementation(() => new Promise((done) => { resolve = done }))
  const { result } = renderHook(() => useSavedRoute(1, 5))
  const saved = { version_number: 2 }
  act(() => result.current[1](saved))
  await act(async () => resolve(late))
  expect(result.current[0]).toEqual(saved)
})

it('fences responses from a previous layout', async () => {
  const pending = []
  routingRequest.mockImplementation(() => new Promise((resolve) => pending.push(resolve)))
  const { result, rerender } = renderHook(({ layout }) => useSavedRoute(1, layout), { initialProps: { layout: 5 } })
  rerender({ layout: 6 })
  await act(async () => pending[1]({ version_number: 3 }))
  await act(async () => pending[0]({ version_number: 1 }))
  expect(result.current[0]).toEqual({ version_number: 3 })
})
