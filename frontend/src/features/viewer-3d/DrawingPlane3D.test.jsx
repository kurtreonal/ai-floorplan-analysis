/* @vitest-environment jsdom */
import { afterEach, expect, it, vi } from 'vitest'
import { PerspectiveCamera, Ray, Vector3 } from 'three'
import { DrawingPlane3D } from './DrawingPlane3D.jsx'
const harness=vi.hoisted(()=>({three:null,cleanups:[]}))
vi.mock('react',async load=>({...await load(),useMemo:fn=>fn(),useEffect:fn=>{harness.cleanups.push(fn())}}))
vi.mock('@react-three/fiber',()=>({useThree:()=>harness.three}))
afterEach(()=>{for(const fn of harness.cleanups)fn?.();harness.cleanups=[]})
it('owns work-plane pointer hits, uses real rays, rejects drags and restores event filtering',()=>{
  const camera=new PerspectiveCamera(50,1,.01,100)
  camera.position.set(5,8,8);camera.lookAt(5,0,5);camera.updateMatrixWorld()
  const previous=vi.fn(),setEvents=vi.fn()
  harness.three={camera,size:{width:600,height:600},pointer:{x:0,y:0},get:()=>({events:{filter:previous}}),setEvents}
  const drawing={vertices:[],hover:null,config:{sceneElevation:2},pointer:vi.fn()}
  const scene={width:10,depth:10,sourceScale:.1,symbols:[]}
  const tree=DrawingPlane3D({scene,drawing,tool:'wire'}),plane=tree.props.children[0]
  const event={button:0,delta:0,stopPropagation:vi.fn(),ray:new Ray(new Vector3(1,10,2),new Vector3(.5,-1,1))}
  plane.props.onClick(event)
  expect(drawing.pointer).toHaveBeenCalledWith({x:50,y:100},expect.objectContaining({screenScale:expect.any(Number)}),true)
  expect(event.stopPropagation).toHaveBeenCalled()
  const hits=[{object:{name:'device'}},{object:{name:'drawing-work-plane-hit'}}]
  expect(setEvents.mock.calls[0][0].filter(hits)).toEqual([hits[1]])
  drawing.pointer.mockClear()
  plane.props.onClick({...event,delta:10});plane.props.onClick({...event,button:2})
  expect(drawing.pointer).not.toHaveBeenCalled()
  harness.cleanups.pop()()
  expect(setEvents).toHaveBeenLastCalledWith({filter:previous})
})
