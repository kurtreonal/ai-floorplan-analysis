/* @vitest-environment jsdom */

import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Canvas } from '@react-three/fiber'
import { Viewer3DCanvas } from './Viewer3DCanvas.jsx'
import { DraftWiring3D } from './DraftWiring3D.jsx'
import { ViewerCameraControls } from './ViewerCameraControls.jsx'
import { DrawingPlane3D } from './DrawingPlane3D.jsx'
import { CanonicalScene } from './CanonicalScene.jsx'

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
  it('gates click selection after pointer movement/cancel and enables movement only in explicit Move',()=>{
    const select=vi.fn(),move=vi.fn()
    const scene={previewOnly:true,target:[0,0,0],extent:10,elevation:0,walls:[],symbols:[],draftWires:[]}
    const {rerender}=render(<Viewer3DCanvas scene={scene} onSelectSymbol={select} onMoveSymbol={move} onMoveWirePoint={move} />)
    const children=()=>Canvas.mock.calls.at(-1)[0].children
    const renderer=()=>children().find(c=>c?.type===CanonicalScene).props
    expect(renderer().onMoveSymbol).toBeUndefined()
    expect(children().find(c=>c?.type===DraftWiring3D).props.onMoveWirePoint).toBeUndefined()
    const viewport=screen.getByRole('region',{name:'3D viewer'})
    fireEvent.pointerDown(viewport,{button:0,clientX:10,clientY:10});fireEvent.pointerUp(viewport,{button:0,clientX:10,clientY:10})
    renderer().onSelectSymbol('s1',{delta:0,button:0});expect(select).toHaveBeenCalledExactlyOnceWith('s1')
    fireEvent.pointerDown(viewport,{button:0,clientX:10,clientY:10});fireEvent.pointerUp(viewport,{button:0,clientX:40,clientY:10})
    renderer().onSelectSymbol('s2',{delta:30,button:0});expect(select).toHaveBeenCalledTimes(1)
    fireEvent.pointerDown(viewport,{button:0});fireEvent.pointerCancel(viewport)
    renderer().onSelectSymbol('s2',{delta:0});expect(select).toHaveBeenCalledTimes(1)
    rerender(<Viewer3DCanvas scene={scene} navigationMode="transform" onSelectSymbol={select} onMoveSymbol={move} />)
    expect(renderer().onMoveSymbol).toBe(move)
    expect(children().find(c=>c?.type===ViewerCameraControls).props.leftOrbit).toBe(false)
    act(()=>renderer().onDraggingChange(true))
    expect(children().find(c=>c?.type===ViewerCameraControls).props.enabled).toBe(false)
  })
  it('passes exact wall selection to the canonical renderer without changing the scene or camera', () => {
    const scene={target:[0,0,0],extent:10,elevation:0,walls:[],symbols:[]}
    const {rerender}=render(<Viewer3DCanvas scene={scene} selectedWallId="wall-1" />)
    const first=Canvas.mock.calls.at(-1)[0]
    expect(first.children.find(child=>child?.type===CanonicalScene).props).toMatchObject({scene,selectedWallId:'wall-1'})
    rerender(<Viewer3DCanvas scene={scene} selectedWallId="wall-2" />)
    const next=Canvas.mock.calls.at(-1)[0]
    expect(next.children.find(child=>child?.type===CanonicalScene).props.selectedWallId).toBe('wall-2')
    expect(next.camera).toEqual(first.camera)
  })
  it('reserves left drawing gestures while preserving alternate orbit, pan and zoom',()=>{
    const drawing={active:true,enabled:true,vertices:[],settings:{elevation:'2.8',circuit:'',axis:'none'},config:{sceneElevation:2.8},setOption:vi.fn(),finish:vi.fn(),cancel:vi.fn()}
    render(<Viewer3DCanvas scene={{previewOnly:true,target:[0,0,0],extent:10,elevation:0,draftWires:[]}} drawing={drawing} navigationMode="wire" />)
    expect(screen.getByRole('group',{name:'3D drawing controls'})).toBeTruthy()
    const children=Canvas.mock.calls.at(-1)[0].children
    expect(children.find(c=>c?.type===DrawingPlane3D).props.drawing).toBe(drawing)
    expect(children.find(c=>c?.type===ViewerCameraControls).props.enabled).toBe(true)
    expect(children.find(c=>c?.type===ViewerCameraControls).props.leftOrbit).toBe(false)
    expect(children.find(c=>c?.type===DraftWiring3D).props.onMoveWirePoint).toBeUndefined()
  })
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
  it('starts in orbit Select mode and retains explicit free-flight navigation', () => {
    render(<Viewer3DCanvas controlsRef={{current:null}} />)
    expect(screen.getByRole('button',{name:'Orbit'}).getAttribute('aria-pressed')).toBe('false')
    expect(screen.getByText(/Click selects · left-drag orbits/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button',{name:'Orbit'}))
    expect(screen.getByRole('button',{name:'Free fly'}).getAttribute('aria-pressed')).toBe('true')
  })
  it('uses a compact exact-terminal chooser for 3D overlaps and invalidates stale scenes', () => {
    const scene={previewOnly:true,sourceScale:.1,target:[0,0,0],extent:10,elevation:0,walls:[],symbols:[],draftWires:[]}
    const move=vi.fn()
    const {rerender}=render(<Viewer3DCanvas scene={scene} selectedWireId="wire1" onMoveWirePoint={move} navigationMode="transform" />)
    const wiringProps=()=>Canvas.mock.calls.at(-1)[0].children.find(child=>child?.type===DraftWiring3D).props
    const choices=['device-a','device-b'].map(symbolId=>({kind:'device',symbolId,terminalId:'design-anchor',point:{x:10,y:20},displayPosition:[1,.5,2]}))
    // The R3F child requests the HTML chooser after releasing pointer capture.
    const {onChooseWireTarget}=wiringProps()
    act(()=>onChooseWireTarget('wire1',0,choices))
    expect(move).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button',{name:'device-b · design anchor'}))
    expect(move).toHaveBeenCalledExactlyOnceWith('wire1',0,{x:1,y:2},{kind:'device',symbolId:'device-b',terminalId:'design-anchor',point:{x:10,y:20}})
    act(()=>wiringProps().onChooseWireTarget('wire1',0,choices))
    fireEvent.keyDown(screen.getByRole('button',{name:'device-a · design anchor'}),{key:'Escape'})
    expect(screen.queryByRole('group',{name:'Choose connection target'})).toBeNull()
    act(()=>wiringProps().onChooseWireTarget('wire1',0,choices))
    rerender(<Viewer3DCanvas scene={{...scene}} selectedWireId="wire1" onMoveWirePoint={move} navigationMode="transform" />)
    expect(screen.queryByRole('group',{name:'Choose connection target'})).toBeNull()
  })
})
