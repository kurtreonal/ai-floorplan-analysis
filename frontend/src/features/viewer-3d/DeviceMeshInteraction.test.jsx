/* @vitest-environment jsdom */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { Ray, Vector3 } from 'three'
import { DeviceMesh } from './DeviceMesh.jsx'
const state=vi.hoisted(()=>({refs:[],cleanup:[],invalidate:vi.fn()}))
vi.mock('react',async load=>({...await load(),useMemo:fn=>fn(),useState:value=>[value,vi.fn()],useRef:value=>{
  const ref={current:value};state.refs.push(ref);return ref
},useEffect:fn=>state.cleanup.push(fn())}))
vi.mock('@react-three/fiber',()=>({useThree:()=>({invalidate:state.invalidate})}))
beforeEach(()=>{state.refs=[];state.cleanup=[];state.invalidate.mockReset()})
afterEach(()=>{for(const cleanup of state.cleanup)cleanup?.()})
const scene={width:10,depth:10,elevation:0,ceilingElevation:3,walls:[]}
const symbol={id:'s1',position:[2,0,3],classification:{name:'Unknown'}}
const target={setPointerCapture:vi.fn(),hasPointerCapture:()=>true,releasePointerCapture:vi.fn()}
const event=(x=2,z=3,screen=10)=>({button:0,pointerId:1,clientX:screen,clientY:screen,
  ray:new Ray(new Vector3(x,10,z),new Vector3(0,-1,0)),target,stopPropagation:vi.fn(),delta:0})
function mesh(props={}) {
  const tree=DeviceMesh({symbol,scene,...props})
  state.refs[0].current={position:new Vector3(...tree.props.position)}
  return tree.props
}

it('does not select or move on pointerdown in normal Select; the click reaches the intent gate',()=>{
  const select=vi.fn(),move=vi.fn(),dragging=vi.fn(),props=mesh({onSelect:select,onDraggingChange:dragging})
  const click=event()
  props.onPointerDown(click);props.onPointerMove(event(4,5,30));props.onPointerUp(event(4,5,30))
  expect(select).not.toHaveBeenCalled();expect(move).not.toHaveBeenCalled();expect(dragging).not.toHaveBeenCalled()
  props.onClick(click);expect(select).toHaveBeenCalledExactlyOnceWith('s1',click)
})

it('moves only a selected object in explicit Move and commits on release without moving the camera model',()=>{
  const move=vi.fn(),dragging=vi.fn(),props=mesh({selected:true,onMove:move,onDraggingChange:dragging})
  props.onPointerDown(event());props.onPointerMove(event(4,5,30));props.onPointerUp(event(4,5,30))
  expect(dragging.mock.calls.map(c=>c[0])).toEqual([true,false])
  expect(move).toHaveBeenCalledExactlyOnceWith('s1',{x:4,y:5})
  expect(symbol.position).toEqual([2,0,3])
})

it.each(['Escape','blur','cancel'])('cancels explicit movement on %s without committing geometry',kind=>{
  const move=vi.fn(),props=mesh({selected:true,onMove:move,onDraggingChange:vi.fn()})
  props.onPointerDown(event());props.onPointerMove(event(4,5,30))
  if(kind==='Escape')window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))
  else if(kind==='blur')window.dispatchEvent(new Event('blur'))
  else props.onPointerCancel(event(4,5,30))
  props.onPointerUp(event(4,5,30))
  expect(move).not.toHaveBeenCalled()
})

it('does not move an unselected device in Move mode or commit a jitter-sized gesture',()=>{
  const move=vi.fn(),props=mesh({selected:false,onMove:move})
  props.onPointerDown(event());props.onPointerMove(event(4,5,30));props.onPointerUp(event(4,5,30))
  expect(move).not.toHaveBeenCalled()
})
