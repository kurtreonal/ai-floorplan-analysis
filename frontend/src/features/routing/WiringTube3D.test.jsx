import { expect, it, vi } from 'vitest'
import { WiringTube3D } from './WiringTube3D.jsx'
const effects=vi.hoisted(()=>[])
vi.mock('react', async importOriginal => ({...await importOriginal(),useMemo:fn=>fn(),useEffect:fn=>effects.push(fn)}))

it('renders smooth continuous pickable tubes, exact terminal caps, and disposes both geometries',()=>{
  effects.length=0
  const run={points:[[0,3,0],[2,3,0],[2,3,2]],anchors:[],laneOffset:0}
  const onClick=vi.fn(), tree=WiringTube3D({run,radius:.02,color:'#f05a28',onClick})
  const [tube,pick,caps]=tree.props.children
  expect(tube.props.geometry.type).toBe('TubeGeometry')
  expect(tube.props.geometry.parameters.radialSegments).toBe(12)
  expect(tube.props.geometry.parameters.path.curves.some(c=>c.type==='QuadraticBezierCurve3')).toBe(true)
  expect(tube.props.children.props).toMatchObject({roughness:.3,metalness:.15})
  expect(caps.map(c=>c.props.position)).toEqual([run.points[0],run.points.at(-1)])
  expect(pick.props.geometry.parameters.radius).toBeCloseTo(.044)
  expect(tree.props.onClick).toBe(onClick)
  tree.props.onPointerDown({button:2})
  expect(onClick).not.toHaveBeenCalled()
  const pointer={button:0}
  tree.props.onPointerDown(pointer)
  expect(onClick).toHaveBeenCalledWith(pointer)
  const dispose=vi.spyOn(tube.props.geometry,'dispose'), disposePick=vi.spyOn(pick.props.geometry,'dispose')
  effects.forEach(effect=>effect()())
  expect(dispose).toHaveBeenCalledOnce();expect(disposePick).toHaveBeenCalledOnce()
})
it('keeps X-ray explicit and retains exact underground depth',()=>{
  const run={points:[[0,-.4,0],[2,-.4,0]],anchors:[]}
  const normal=WiringTube3D({run,radius:.02,color:'#2563eb'}).props.children[0]
  const xray=WiringTube3D({run,radius:.02,color:'#2563eb',xray:true}).props.children[0]
  expect(normal.props.children.props.depthTest).toBeUndefined()
  expect(xray.props.children.props).toMatchObject({depthTest:false,depthWrite:false})
  expect(xray.props.renderOrder).toBe(10)
  expect(xray.props.geometry.parameters.path.getPoint(.5).y).toBe(-.4)
})
