/* @vitest-environment jsdom */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { PerspectiveCamera, Ray, Vector3 } from 'three'
import { WireHandle } from './DraftWiring3D.jsx'

const harness = vi.hoisted(() => ({refs:[],cleanups:[],setState:vi.fn(),three:null}))
vi.mock('react', async load => ({...await load(), useRef:()=>harness.refs.shift(),
  useState:()=>[null,harness.setState], useEffect:fn=>{ const cleanup=fn(); if (cleanup) harness.cleanups.push(cleanup) }}))
vi.mock('@react-three/fiber',()=>({useThree:()=>harness.three,useFrame:()=>{}}))
beforeEach(()=>{
  const camera = new PerspectiveCamera(50,1,.01,100)
  camera.position.set(5,8,8); camera.lookAt(5,0,5); camera.updateMatrixWorld()
  harness.three = {camera,pointer:{x:0,y:0},size:{width:600,height:600},invalidate:vi.fn()}
  harness.setState.mockClear()
})
afterEach(()=>{for (const cleanup of harness.cleanups) cleanup(); harness.cleanups=[]})

function handle(findSnap=vi.fn(()=>null)) {
  const position=[1,.75,2], node={position:new Vector3(...position)}
  harness.refs=[{current:node},{current:null},{current:null}]
  const move=vi.fn(), dragging=vi.fn()
  const scene={sourceScale:.025,width:10,depth:10,unitsPerMeter:.25,walls:[],symbols:[
    {id:'s',position:[3,0,2],presentation:{family:'troffer'}}],ceilingElevation:.75}
  const tree=WireHandle({position,scene,onMove:move,onFindSnap:findSnap,onDraggingChange:dragging})
  const props=tree.props.children[0].props
  const target={setPointerCapture:vi.fn(),releasePointerCapture:vi.fn()}
  const event=x=>({pointerId:1,button:0,target,stopPropagation:vi.fn(),
    ray:new Ray(new Vector3(x,5,2),new Vector3(0,-1,0))})
  return {props,move,dragging,node,event,findSnap}
}

it('magnetizes a captured 3D handle and commits the explicit shared attachment on release',()=>{
  const snap={symbolId:'s',point:{x:120,y:80},distance:4}
  const find=vi.fn((point,distance)=>{ expect(Number.isFinite(distance({id:'s'}))).toBe(true); return snap })
  const h=handle(find)
  h.props.onPointerDown(h.event(1))
  h.props.onPointerMove(h.event(2.9))
  expect(h.node.position.toArray()).toEqual([3,.75,2])
  expect(harness.setState).toHaveBeenCalledWith(expect.objectContaining({position:expect.any(Array)}))
  h.props.onPointerUp(h.event(2.9))
  expect(h.move).toHaveBeenCalledWith({x:3,y:2},snap)
  expect(h.dragging.mock.calls.map(c=>c[0])).toEqual([true,false])
})

it('cancels on Escape and pointer cancellation without saving or moving a device',()=>{
  for (const keyboard of [true,false]) {
    const h=handle(()=>({symbolId:'s',point:{x:120,y:80}}))
    h.props.onPointerDown(h.event(1)); h.props.onPointerMove(h.event(2.9))
    if (keyboard) window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))
    else h.props.onPointerCancel(h.event(2.9))
    h.props.onPointerUp(h.event(2.9))
    expect(h.move).not.toHaveBeenCalled()
    expect(h.node.position.toArray()).toEqual([1,.75,2])
  }
})

it('does not propose a device behind the camera and permits ordinary unsnapped movement',()=>{
  const h=handle((point,distance)=>{ expect(distance({id:'s'})).toBe(Infinity); return null })
  harness.three.camera.lookAt(5,8,30); harness.three.camera.updateMatrixWorld()
  h.props.onPointerDown(h.event(1)); h.props.onPointerMove(h.event(2.5)); h.props.onPointerUp(h.event(2.5))
  expect(h.move).toHaveBeenCalledWith({x:2.5,y:2})
})
