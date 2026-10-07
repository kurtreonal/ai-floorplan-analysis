/* @vitest-environment jsdom */
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { routingRequest } from '../../api/routing.js'
import { useSavedRoute } from './useSavedRoute.js'
vi.mock('../../api/routing.js', () => ({ routingRequest: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks() })

it.each([null, { project_id: 1, version_number: 1 }])('preserves a newly saved route against a late response: %s', async (late) => {
  let resolve
  routingRequest.mockImplementation(() => new Promise((done) => { resolve = done }))
  const { result } = renderHook(() => useSavedRoute(1, 5))
  const saved = { project_id: 1, version_number: 2 }
  act(() => result.current[1](saved))
  await act(async () => resolve(late))
  expect(result.current[0]).toEqual(saved)
})

it('fences responses from a previous layout', async () => {
  const pending = []
  routingRequest.mockImplementation(() => new Promise((resolve) => pending.push(resolve)))
  const { result, rerender } = renderHook(({ layout }) => useSavedRoute(1, layout), { initialProps: { layout: 5 } })
  rerender({ layout: 6 })
  await act(async () => pending[1]({ project_id: 1, version_number: 3 }))
  await act(async () => pending[0]({ project_id: 1, version_number: 1 }))
  expect(result.current[0]).toEqual({ project_id: 1, version_number: 3 })
})

it('does not downgrade a saved version on late POST, retry replay or initial GET', async () => {
  let finish
  routingRequest.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  const hook = renderHook(() => useSavedRoute(1, 5))
  const saved = { project_id: 1, version_number: 3 }
  act(() => hook.result.current[1](saved))
  act(() => hook.result.current[1]({ project_id: 1, version_number: 2 }))
  act(() => hook.result.current[1]({ project_id: 9, version_number: 4 }))
  await act(async () => finish({ project_id: 1, version_number: 1 }))
  expect(hook.result.current[0]).toBe(saved)
})

it('resets to the newly loaded layout scope and aborts obsolete GET requests', async () => {
  routingRequest.mockResolvedValue({ project_id: 1, version_number: 2 })
  const hook = renderHook(({ id }) => useSavedRoute(1, id), { initialProps: { id: 5 } })
  await waitFor(() => expect(hook.result.current[0]?.version_number).toBe(2))
  const signal = routingRequest.mock.calls[0][1].signal
  routingRequest.mockResolvedValue({ project_id: 1, version_number: 3 })
  hook.rerender({ id: 6 })
  expect(signal.aborted).toBe(true)
  await waitFor(() => expect(hook.result.current[0]?.version_number).toBe(3))
})

it('rejects a late save callback captured by a previous layout render', async () => {
  routingRequest.mockResolvedValue({ project_id: 1, version_number: 2 })
  const hook = renderHook(({ id }) => useSavedRoute(1, id), { initialProps: { id: 5 } })
  await waitFor(() => expect(hook.result.current[0]?.version_number).toBe(2))
  const oldSetter = hook.result.current[1]
  routingRequest.mockResolvedValue({ project_id: 1, version_number: 3 })
  hook.rerender({ id: 6 })
  await waitFor(() => expect(hook.result.current[0]?.version_number).toBe(3))
  act(() => oldSetter({ project_id: 1, version_number: 99 }))
  expect(hook.result.current[0]?.version_number).toBe(3)
})
