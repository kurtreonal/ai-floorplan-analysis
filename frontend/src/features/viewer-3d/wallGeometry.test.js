import {expect,it} from 'vitest'
import {buildWallTopology} from '../../geometry/wallTopology.js'
import {joinedWallGeometry} from './wallGeometry.js'
it('emits no internal T end caps and keeps exterior faces/top normals',()=>{
  const rows=[{id:'a',start:{x:0,y:0},end:{x:20,y:0},thickness:2,height:3,elevation:0},
    {id:'b',start:{x:10,y:0},end:{x:10,y:10},thickness:2,height:3,elevation:0}]
  const wall=buildWallTopology(rows).walls[1],geometry=joinedWallGeometry(wall)
  const positions=geometry.attributes.position,normals=geometry.attributes.normal
  const triangles=[]
  for(let i=0;i<positions.count;i+=3)triangles.push([0,1,2].map(k=>[positions.getX(i+k),positions.getY(i+k),positions.getZ(i+k)]))
  expect(triangles.some(t=>t.every(p=>Math.abs(p[2]+1)<1e-6))).toBe(false)
  expect(triangles.some(t=>t.every(p=>p[1]===3))).toBe(true)
  expect(Array.from(normals.array).every(Number.isFinite)).toBe(true)
  expect(geometry.boundingBox.min.y).toBe(0);expect(geometry.boundingBox.max.y).toBe(3)
  geometry.dispose()
})
