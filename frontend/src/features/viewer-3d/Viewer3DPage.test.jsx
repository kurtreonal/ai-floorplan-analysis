/* @vitest-environment jsdom */

import { useEffect } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import Viewer3DPage from './Viewer3DPage.jsx'

const mocks = vi.hoisted(() => ({ reset: vi.fn(), canvasRenders: vi.fn() }))

vi.mock('./Viewer3DCanvas.jsx', () => ({
  Viewer3DCanvas: ({ controlsRef, onControlsReady }) => {
    useEffect(() => {
      controlsRef.current = { reset: mocks.reset }
      onControlsReady(true)
      return () => {
        controlsRef.current = null
        onControlsReady(false)
      }
    }, [controlsRef, onControlsReady])
    mocks.canvasRenders()
    return <div data-testid="viewer-canvas" />
  },
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('3D viewer page', () => {
  it('renders an intentionally empty floor-scoped workspace without API requests', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    render(<Viewer3DPage projectId={15} projectFloorId={2} />)
    expect(screen.getByRole('heading', { name: '3D planning workspace' })).toBeTruthy()
    expect(screen.getByText(/FLOOR #2/)).toBeTruthy()
    expect(screen.getByRole('note').textContent).toMatch(/intentionally not loaded yet/)
    expect(screen.getByRole('link', { name: /Back to project/ }).getAttribute('href')).toBe('#/app/projects/15')
    expect(fetchSpy).not.toHaveBeenCalled()
    fetchSpy.mockRestore()
  })

  it('resets the camera and can restart only the canvas subtree', () => {
    render(<Viewer3DPage projectId={15} projectFloorId={2} />)
    const reset = screen.getByRole('button', { name: 'Reset view' })
    expect(reset.disabled).toBe(false)
    fireEvent.click(reset)
    expect(mocks.reset).toHaveBeenCalledOnce()
    expect(screen.getByText('3D camera reset to its initial view.')).toBeTruthy()
    const renders = mocks.canvasRenders.mock.calls.length
    fireEvent.click(screen.getByRole('button', { name: 'Restart 3D canvas' }))
    expect(mocks.canvasRenders.mock.calls.length).toBeGreaterThan(renders)
  })
})
