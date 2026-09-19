/* @vitest-environment jsdom */

import { useEffect } from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import Viewer3DPage from './Viewer3DPage.jsx'
import fixture from '../../../../fixtures/canonical_geometry_v1.json'
import { fetchCurrentLayout } from '../../api/layouts.js'
vi.mock('../../api/layouts.js', () => ({ fetchCurrentLayout: vi.fn() }))

const mocks = vi.hoisted(() => ({ reset: vi.fn(), canvasRenders: vi.fn() }))

vi.mock('./Viewer3DCanvas.jsx', () => ({
  Viewer3DCanvas: ({ controlsRef, onControlsReady, scene }) => {
    useEffect(() => {
      controlsRef.current = { reset: mocks.reset }
      onControlsReady(true)
      return () => {
        controlsRef.current = null
        onControlsReady(false)
      }
    }, [controlsRef, onControlsReady])
    mocks.canvasRenders(scene)
    return <div data-testid="viewer-canvas" />
  },
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('3D viewer page', () => {
  it('loads the same saved canonical snapshot as 2D', async () => {
    const geometry = structuredClone(fixture)
    Object.assign(geometry.walls[0], { status: 'verified', height_meters: 3, thickness_meters: 0.15 })
    fetchCurrentLayout.mockResolvedValue({ version_number: 4, geometry })
    render(<Viewer3DPage projectId={15} projectFloorId={2} />)
    await screen.findByTestId('viewer-canvas')
    expect(screen.getByRole('heading', { name: '3D planning workspace' })).toBeTruthy()
    expect(screen.getByText(/FLOOR #2/)).toBeTruthy()
    expect(screen.getByText(/Saved version 4/)).toBeTruthy()
    expect(screen.getByRole('link', { name: /Back to project/ }).getAttribute('href')).toBe('#/app/projects/15')
    expect(fetchCurrentLayout).toHaveBeenCalledWith(15, 2, expect.objectContaining({ signal: expect.any(AbortSignal) }))
  })

  it('resets the camera and reloads persisted geometry', async () => {
    const geometry = structuredClone(fixture)
    Object.assign(geometry.walls[0], { status: 'verified', height_meters: 3, thickness_meters: 0.15 })
    fetchCurrentLayout.mockResolvedValue({ version_number: 4, geometry })
    render(<Viewer3DPage projectId={15} projectFloorId={2} />)
    await screen.findByTestId('viewer-canvas')
    const reset = screen.getByRole('button', { name: 'Reset view' })
    await waitFor(() => expect(reset.disabled).toBe(false))
    fireEvent.click(reset)
    expect(mocks.reset).toHaveBeenCalledOnce()
    expect(screen.getByText('3D camera reset to its initial view.')).toBeTruthy()
    const renders = mocks.canvasRenders.mock.calls.length
    fireEvent.click(screen.getByRole('button', { name: 'Restart 3D canvas' }))
    await waitFor(() => expect(mocks.canvasRenders.mock.calls.length).toBeGreaterThan(renders))
  })
  it('shows missing layout and does not render an empty success scene', async () => {
    fetchCurrentLayout.mockRejectedValue({ status: 404 })
    render(<Viewer3DPage projectId={15} projectFloorId={2} />)
    expect((await screen.findByRole('alert')).textContent).toMatch(/No saved layout/)
    expect(screen.queryByTestId('viewer-canvas')).toBeNull()
  })
  it('reloads changed saved positions and removes deleted records from the scene', async () => {
    const geometry = structuredClone(fixture)
    geometry.walls = []
    fetchCurrentLayout.mockResolvedValueOnce({ version_number: 4, geometry })
    render(<Viewer3DPage projectId={15} projectFloorId={2} />)
    await screen.findByText(/Saved version 4/)
    const updated = structuredClone(geometry)
    updated.symbols[0].position = { x: 3, y: 2 }
    updated.symbols.pop()
    fetchCurrentLayout.mockResolvedValueOnce({ version_number: 5, geometry: updated })
    fireEvent.click(screen.getByRole('button', { name: 'Reload saved layout' }))
    expect(screen.queryByTestId('viewer-canvas')).toBeNull()
    await screen.findByText(/Saved version 5/)
    const scene = mocks.canvasRenders.mock.calls.at(-1)[0]
    expect(scene.symbols).toHaveLength(1)
    expect(scene.symbols[0].position).toEqual([3, -1.5, 2])
    expect(screen.getByText(/Power outlet \(class 7\)/)).toBeTruthy()
  })
  it('clears the previous scene when reload fails', async () => {
    const geometry = structuredClone(fixture)
    geometry.walls = []
    fetchCurrentLayout.mockResolvedValueOnce({ version_number: 4, geometry })
    render(<Viewer3DPage projectId={15} projectFloorId={2} />)
    await screen.findByTestId('viewer-canvas')
    fetchCurrentLayout.mockRejectedValueOnce({ status: 403 })
    fireEvent.click(screen.getByRole('button', { name: 'Reload saved layout' }))
    await screen.findByRole('alert')
    expect(screen.queryByTestId('viewer-canvas')).toBeNull()
    expect(screen.queryByText(/Saved version 4/)).toBeNull()
  })
  it('aborts the previous floor request and fences its late response', async () => {
    let resolveOld
    fetchCurrentLayout.mockReturnValueOnce(new Promise((resolve) => { resolveOld = resolve }))
    const { rerender } = render(<Viewer3DPage projectId={15} projectFloorId={2} />)
    const oldSignal = fetchCurrentLayout.mock.calls.at(-1)[2].signal
    fetchCurrentLayout.mockRejectedValueOnce({ status: 404 })
    rerender(<Viewer3DPage projectId={15} projectFloorId={3} />)
    await screen.findByRole('alert')
    expect(oldSignal.aborted).toBe(true)
    resolveOld({ version_number: 99, geometry: fixture })
    await waitFor(() => expect(screen.queryByText(/Saved version 99/)).toBeNull())
    expect(screen.queryByTestId('viewer-canvas')).toBeNull()
  })
})
