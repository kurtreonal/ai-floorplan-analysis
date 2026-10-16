/* @vitest-environment jsdom */
import {act,cleanup,fireEvent,render} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
const shapes=vi.hoisted(()=>new Map())
vi.mock('react-konva',()=>{
  const container=({children})=><div>{children}</div>
  const shape=props=>{if(props.name)shapes.set(props.name,props);return null}
  return {Stage:container,Layer:container,Group:container,Image:shape,Line:shape,Rect:shape,Circle:shape,Text:shape,Arrow:shape}
})
import {DemoInterpretationCanvas} from './DemoInterpretationCanvas.jsx'
afterEach(()=>{cleanup();shapes.clear()})
function setup(tool='select') {
  const move=vi.fn(),draft={walls:[],rooms:[],symbols:[],wirings:[
    {id:'segment-0001',points:[{x:0,y:0},{x:8,y:8}],device_attachments:[],disposition:'unresolved'},
    {id:'segment-0002',points:[{x:10,y:0},{x:10,y:20}],device_attachments:[],disposition:'unresolved'}]}
  render(<DemoInterpretationCanvas width={100} height={100} draft={draft} selected={{kind:'wiring',id:'segment-0001'}}
    layers={{wirings:true}} tool={tool} onMoveWirePoint={move} />)
  const handle=shapes.get('wiring-point-1')
  let point={x:9,y:9}
  const node={x:()=>point.x,y:()=>point.y,position:p=>{point=p},stopDrag:vi.fn()}
  return {move,handle,node}
}
it('shows path magnet on pointer movement and commits it only on release',()=>{
  const {move,handle,node}=setup()
  act(()=>handle.onDragStart({target:node}))
  act(()=>handle.onDragMove({target:node}))
  expect(shapes.get('wire-device-magnet')).toMatchObject({x:10,y:9})
  expect(move).not.toHaveBeenCalled()
  act(()=>handle.onDragEnd({target:node}))
  expect(move).toHaveBeenCalledWith('segment-0001',1,{x:10,y:9},expect.objectContaining({kind:'junction',wireId:'segment-0002'}))
})
it('Escape cancels a preview without committing an attachment and pan disables dragging',()=>{
  const {move,handle,node}=setup()
  act(()=>handle.onDragStart({target:node}))
  act(()=>handle.onDragMove({target:node}))
  fireEvent.keyDown(window,{key:'Escape'})
  act(()=>handle.onDragEnd({target:node}))
  expect(move).not.toHaveBeenCalled();expect(node.stopDrag).toHaveBeenCalled()
  cleanup();shapes.clear()
  expect(setup('pan').handle.draggable).toBe(false)
})
