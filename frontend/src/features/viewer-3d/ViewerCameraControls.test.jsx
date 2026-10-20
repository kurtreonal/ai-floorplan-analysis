/* @vitest-environment jsdom */

import { StrictMode } from 'react'
import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ViewerCameraControls } from './ViewerCameraControls.jsx'
import { MOUSE, TOUCH, Quaternion, Vector3 } from 'three'

const mocks = vi.hoisted(() => ({
  camera: { name: 'camera', position: { set: vi.fn() } },
  domElement: document.createElement('canvas'),
  invalidate: vi.fn(),
  instances: [],
  frame: null,
}))

vi.mock('@react-three/fiber', () => ({
  useFrame: fn => { mocks.frame = fn },
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
        camera, domElement, target: new Vector3(2,1,3), update: vi.fn(), saveState: vi.fn(),
        reset: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispose: vi.fn(), mouseButtons: {}, touches:{},
      })
      vi.spyOn(this.target,'set')
      mocks.instances.push(this)
    }
  },
}))

beforeEach(() => {
  mocks.instances.length = 0
  mocks.invalidate.mockReset()
  mocks.camera.position = new Vector3(2,8,10)
  mocks.camera.quaternion = new Quaternion()
  vi.spyOn(mocks.camera.position,'set')
  mocks.frame = null
})

afterEach(cleanup)

describe('3D camera controls', () => {
  it('uses left orbit in Select, reserves editing clicks, and retains alternate desktop/touch camera gestures',()=>{
    const view=render(<ViewerCameraControls freeFly={false}/>)
    const controls=mocks.instances[0]
    expect(controls.mouseButtons).toEqual({LEFT:MOUSE.ROTATE,MIDDLE:MOUSE.ROTATE,RIGHT:MOUSE.PAN})
    expect(controls.touches).toEqual({ONE:TOUCH.ROTATE,TWO:TOUCH.DOLLY_PAN})
    view.rerender(<ViewerCameraControls freeFly={false} leftOrbit={false}/>)
    expect(mocks.instances).toHaveLength(1)
    expect(controls.mouseButtons.LEFT).toBeNull()
    expect(controls.mouseButtons.MIDDLE).toBe(MOUSE.ROTATE)
    expect(controls.touches).toEqual({ONE:null,TWO:TOUCH.DOLLY_ROTATE})
    expect(controls.enableZoom).toBe(true);expect(controls.enablePan).toBe(true)
  })
  it('moves only the focused viewport, ignores input/disabled controls and cleans up its keyboard listener', () => {
    const viewport = document.createElement('section'), input = document.createElement('input')
    viewport.setAttribute('aria-label','3D viewer'); viewport.tabIndex = 0
    viewport.append(mocks.domElement,input); document.body.append(viewport)
    vi.spyOn(mocks.camera.position,'add')
    const view = render(<ViewerCameraControls extent={20} />)
    const controls = mocks.instances[0]
    vi.spyOn(controls.target,'add')
    fireEvent.keyDown(viewport,{key:'w'})
    expect(mocks.camera.position.add).not.toHaveBeenCalled()
    viewport.focus(); fireEvent.keyDown(viewport,{key:'ArrowUp'})
    expect(mocks.camera.position.add).not.toHaveBeenCalled()
    mocks.frame({},1/60)
    expect(mocks.camera.position.add).toHaveBeenCalledOnce()
    expect(controls.target.add).toHaveBeenCalledWith(mocks.camera.position.add.mock.calls[0][0])
    expect(mocks.camera.position.add.mock.calls[0][0].z).toBeLessThan(0)
    input.focus(); fireEvent.keyDown(input,{key:'w'})
    mocks.frame({},1/60)
    expect(mocks.camera.position.add).toHaveBeenCalledOnce()
    view.rerender(<ViewerCameraControls extent={20} enabled={false} />)
    viewport.focus(); fireEvent.keyDown(viewport,{key:'d'})
    mocks.frame({},1/60)
    expect(mocks.camera.position.add).toHaveBeenCalledOnce()
    view.unmount(); fireEvent.keyDown(viewport,{key:'a'})
    mocks.frame({},1/60)
    expect(mocks.camera.position.add).toHaveBeenCalledOnce()
    viewport.remove()
  })
  it('enables orbit, pan, and zoom, resets deterministically, and disposes listeners', () => {
    const controlsRef = { current: null }
    const onReady = vi.fn()
    const view = render(<ViewerCameraControls ref={controlsRef} onReady={onReady} freeFly={false} />)
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

  it('holds keys across frames, ignores OS repeats, sprints, releases and stops on window blur', () => {
    const viewport = document.createElement('section')
    viewport.setAttribute('aria-label','3D viewer'); viewport.tabIndex=0
    viewport.append(mocks.domElement); document.body.append(viewport)
    const ref = {current:null}
    const view = render(<ViewerCameraControls ref={ref} extent={20} />)
    viewport.focus()
    fireEvent.keyDown(viewport,{key:'w'})
    mocks.frame({},1/60)
    const first = mocks.camera.position.clone()
    fireEvent.keyDown(viewport,{key:'w',repeat:true})
    mocks.frame({},1/60)
    expect(first.distanceTo(mocks.camera.position)).toBeGreaterThan(0)
    ref.current.reset()
    const start = mocks.camera.position.clone()
    fireEvent.keyDown(viewport,{key:'w',shiftKey:true})
    mocks.frame({},1/60)
    const sprint = start.distanceTo(mocks.camera.position)
    ref.current.reset()
    const ordinaryStart = mocks.camera.position.clone()
    fireEvent.keyDown(viewport,{key:'w'})
    mocks.frame({},1/60)
    expect(sprint/ordinaryStart.distanceTo(mocks.camera.position)).toBeCloseTo(3)
    fireEvent.keyUp(window,{key:'w'})
    for(let i=0;i<120;i++) mocks.frame({},1/60)
    const stopped = mocks.camera.position.clone(), invalidations = mocks.invalidate.mock.calls.length
    mocks.frame({},1/60)
    expect(mocks.camera.position).toEqual(stopped)
    expect(mocks.invalidate).toHaveBeenCalledTimes(invalidations)
    fireEvent.keyDown(viewport,{key:'w'}); fireEvent.blur(window)
    mocks.frame({},1/60)
    expect(mocks.camera.position).toEqual(stopped)
    view.rerender(<ViewerCameraControls ref={ref} extent={20} freeFly={false} />)
    fireEvent.keyDown(viewport,{key:'w'}); mocks.frame({},1/60)
    expect(mocks.camera.position).toEqual(stopped)
    expect(mocks.instances[0].enableRotate).toBe(true)
    view.unmount(); viewport.remove()
  })

  it('right-drag turns the spectator in place and does not orbit or move devices', () => {
    const view = render(<ViewerCameraControls extent={20} />)
    const position = mocks.camera.position.clone(), facing = mocks.camera.quaternion.clone()
    const dispatch = (type, x, y) => mocks.domElement.dispatchEvent(new MouseEvent(type,{button:2,clientX:x,clientY:y,bubbles:true,cancelable:true}))
    dispatch('pointerdown',20,20); dispatch('pointermove',70,35); dispatch('pointerup',70,35)
    expect(mocks.camera.position).toEqual(position)
    expect(mocks.camera.quaternion).not.toEqual(facing)
    expect(mocks.instances[0].enableRotate).toBe(false)
    const turned = mocks.camera.quaternion.clone()
    dispatch('pointermove',90,80)
    expect(mocks.camera.quaternion).toEqual(turned)
    view.unmount()
    dispatch('pointerdown',20,20); dispatch('pointermove',70,35)
    expect(mocks.camera.quaternion).toEqual(turned)
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
