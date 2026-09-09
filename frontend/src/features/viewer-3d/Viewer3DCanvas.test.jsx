/* @vitest-environment jsdom */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Canvas } from '@react-three/fiber'
import { Viewer3DCanvas } from './Viewer3DCanvas.jsx'

vi.mock('@react-three/fiber', () => ({
  Canvas: vi.fn(({ fallback, frameloop }) => (
    <div data-testid="r3f-canvas" data-frameloop={frameloop}>{fallback}</div>
  )),
}))
vi.mock('./ViewerCameraControls.jsx', () => ({ ViewerCameraControls: () => null }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('3D canvas foundation', () => {
  it('uses demand rendering, a bounded camera, and a visible WebGL fallback', () => {
    render(<Viewer3DCanvas controlsRef={{ current: null }} onControlsReady={vi.fn()} />)
    expect(screen.getByRole('region', { name: '3D viewer' })).toBeTruthy()
    expect(screen.getByTestId('r3f-canvas').dataset.frameloop).toBe('demand')
    expect(screen.getByRole('status').textContent).toMatch(/WebGL canvas/)
    expect(Canvas).toHaveBeenCalledWith(
      expect.objectContaining({
        frameloop: 'demand',
        camera: { position: [8, 6, 8], fov: 50, near: 0.01, far: 1000 },
      }),
      undefined,
    )
  })
})
