/* @vitest-environment jsdom */

import { StrictMode } from 'react'
import { cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ViewerCameraControls } from './ViewerCameraControls.jsx'
import { MOUSE } from 'three'

const mocks = vi.hoisted(() => ({
  camera: { name: 'camera', position: { set: vi.fn() } },
  domElement: document.createElement('canvas'),
  invalidate: vi.fn(),
  instances: [],
}))

vi.mock('@react-three/fiber', () => ({
  useThree: () => ({
    camera: mocks.camera,
    gl: { domElement: mocks.domElement },
    invalidate: mocks.invalidate,
  }),
}))

vi.mock('three/addons/controls/OrbitControls.js', () => ({
  OrbitControls: class OrbitControls {
    constructor(camera, domElement) {
      Object.assign(this, {
        camera, domElement, target: { x: 2, y: 1, z: 3, set: vi.fn() }, update: vi.fn(), saveState: vi.fn(),
        reset: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispose: vi.fn(), mouseButtons: {},
      })
      mocks.instances.push(this)
    }
  },
}))

beforeEach(() => {
  mocks.instances.length = 0
  mocks.invalidate.mockReset()
  mocks.camera.position.set.mockReset()
})

afterEach(cleanup)

describe('3D camera controls', () => {
  it('enables orbit, pan, and zoom, resets deterministically, and disposes listeners', () => {
    const controlsRef = { current: null }
    const onReady = vi.fn()
    const view = render(<ViewerCameraControls ref={controlsRef} onReady={onReady} />)
    const controls = mocks.instances[0]

    expect(controls.camera).toBe(mocks.camera)
    expect(controls.domElement).toBe(mocks.domElement)
    expect(controls.enableRotate).toBe(true)
    expect(controls.enablePan).toBe(true)
    expect(controls.enableZoom).toBe(true)
    expect(controls.target.set).toHaveBeenCalledWith(0, 0, 0)
    expect(controls.saveState).toHaveBeenCalledOnce()
    expect(controls.addEventListener).toHaveBeenCalledWith('change', mocks.invalidate)
    expect(onReady).toHaveBeenCalledWith(true)

    controlsRef.current.reset()
    expect(controls.reset).toHaveBeenCalledOnce()
    expect(mocks.invalidate).toHaveBeenCalledOnce()

    view.unmount()
    expect(controls.removeEventListener).toHaveBeenCalledWith('change', mocks.invalidate)
    expect(controls.dispose).toHaveBeenCalledOnce()
    expect(onReady).toHaveBeenCalledWith(false)
  })

  it('leaves no duplicate active controls through StrictMode setup and cleanup', () => {
    const view = render(
      <StrictMode>
        <ViewerCameraControls ref={{ current: null }} onReady={vi.fn()} />
      </StrictMode>,
    )
    expect(mocks.instances.length).toBeGreaterThanOrEqual(2)
    const active = mocks.instances.filter((controls) => controls.dispose.mock.calls.length === 0)
    expect(active).toHaveLength(1)
    view.unmount()
    expect(mocks.instances.every((controls) => controls.dispose.mock.calls.length === 1)).toBe(true)
  })
  it('changes pan/drag modes without rebuilding camera controls or resetting a device selection', () => {
    const ref = { current: null }
    const { rerender } = render(<ViewerCameraControls ref={ref} target={[2, 1, 3]} extent={10} />)
    const controls = mocks.instances[0]
    rerender(<ViewerCameraControls ref={ref} target={[2, 1, 3]} extent={10} enabled={false} panMode />)
    expect(mocks.instances).toHaveLength(1)
    expect(controls.enabled).toBe(false)
    expect(controls.mouseButtons.LEFT).toBe(MOUSE.PAN)
    rerender(<ViewerCameraControls ref={ref} target={[2, 1, 3]} extent={10} />)
    expect(controls.enabled).toBe(true)
    expect(controls.mouseButtons.LEFT).toBe(MOUSE.ROTATE)
    ref.current.top()
    expect(mocks.camera.position.set).toHaveBeenLastCalledWith(2, 17, 3.001)
    ref.current.front()
    expect(mocks.camera.position.set).toHaveBeenLastCalledWith(2, 4, 19)
  })
})
