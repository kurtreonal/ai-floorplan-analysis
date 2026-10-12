import {expect,it} from 'vitest'
import {buildWallTopology,moveJoinedWall,sceneWallTopology} from './wallTopology.js'
const wall=(id,a,b,width=2)=>({id,start:{x:a[0],y:a[1]},end:{x:b[0],y:b[1]},thickness:width})
const area=p=>Math.abs(p.reduce((s,a,i)=>s+a.x*p[(i+1)%p.length].y-a.y*p[(i+1)%p.length].x,0))/2
it.each([
  ['L',[wall('a',[0,0],[10,0]),wall('b',[10,0],[10,10])]],
  ['T',[wall('a',[0,0],[20,0]),wall('b',[10,0],[10,10])]],
  ['X',[wall('a',[0,0],[20,0]),wall('b',[10,-10],[10,10])]],
  ['angled',[wall('a',[0,0],[10,0]),wall('b',[10,0],[17,7])]],
])('keeps %s wall identities with nonoverlapping joined footprints',(_,walls)=>{
  const before=structuredClone(walls),result=buildWallTopology(walls)
  expect(result.junctions).not.toHaveLength(0)
  expect(result.walls.map(w=>w.id)).toEqual(walls.map(w=>w.id))
  expect(result.walls.every(w=>w.footprints.every(p=>area(p)>0))).toBe(true)
  expect(walls).toEqual(before)
  const fullArea=result.walls.reduce((s,w)=>s+w.footprints.reduce((v,p)=>v+area(p),0),0)
  expect(fullArea).toBeLessThan(walls.reduce((s,w)=>s+Math.hypot(w.end.x-w.start.x,w.end.y-w.start.y)*w.thickness,0)+8)
  if(_==='T')expect(fullArea).toBe(58)
  if(_==='X')expect(fullArea).toBe(76)
})
it('removes internal T caps without hiding exterior edges',()=>{
  const result=buildWallTopology([wall('a',[0,0],[20,0]),wall('b',[10,0],[10,10])])
  expect(result.walls[1].boundary.some(edge=>edge.every(p=>Math.abs(p.y+1)<1e-6))).toBe(false)
  expect(result.walls[1].boundary.some(edge=>edge.every(p=>Math.abs(p.y-10)<1e-6))).toBe(true)
})
it('preserves door gaps and nearby separate parallel walls',()=>{
  const rows=[wall('a',[0,0],[10,0]),wall('b',[10.2,0],[20,0]),wall('c',[0,1.5],[10,1.5])]
  const result=buildWallTopology(rows)
  expect(result.junctions).toEqual([])
  expect(result.walls.every(w=>w.footprints.length===1&&w.boundary.length===4)).toBe(true)
})
it('deduplicates collinear overlap in display without deleting either wall',()=>{
  const result=buildWallTopology([wall('a',[0,0],[20,0]),wall('b',[5,0],[15,0])])
  expect(result.walls[1].footprints).toEqual([])
  expect(result.walls).toHaveLength(2)
})
it('moves exact shared ends and body junctions, preserves nearby endpoints and reloads deterministically',()=>{
  const rows=[wall('a',[0,0],[20,0]),wall('b',[10,0],[10,10]),wall('c',[20,0],[20,10]),wall('d',[10,.1],[10,8])]
  const result=moveJoinedWall(rows,{...rows[0],start:{x:0,y:3},end:{x:20,y:3}})
  expect(result[1].start).toEqual({x:10,y:3});expect(result[2].start).toEqual({x:20,y:3})
  expect(result[3].start).toEqual(rows[3].start)
  expect(buildWallTopology(JSON.parse(JSON.stringify(result)))).toEqual(buildWallTopology(result))
})
it('uses identical source footprints when projected to scene units',()=>{
  const rows=[wall('a',[0,0],[20,0]),wall('b',[10,0],[10,10])]
  const scene=rows.map(w=>({id:w.id,position:[(w.start.x+w.end.x)/2,1,(w.start.y+w.end.y)/2],
    rotation:[0,-Math.atan2(w.end.y-w.start.y,w.end.x-w.start.x),0],size:[Math.hypot(w.end.x-w.start.x,w.end.y-w.start.y),2,2]}))
  const a=buildWallTopology(rows).walls,b=sceneWallTopology(scene).walls
  for(let i=0;i<a.length;i++)expect(b[i].footprints).toEqual(a[i].footprints)
})
it('keeps a moved T branch attached to its existing support unless explicitly detached',()=>{
  const rows=[wall('a',[0,0],[20,0]),wall('b',[10,0],[10,10])]
  const updated={...rows[1],start:{x:12,y:3},end:{x:12,y:13}}
  const moved=moveJoinedWall(rows,updated)
  expect(moved[0]).toEqual(rows[0]);expect(moved[1].start).toEqual({x:12,y:0})
  expect(buildWallTopology(moved).junctions).toHaveLength(1)
  expect(moveJoinedWall(rows,updated,{detach:true})[1].start).toEqual(updated.start)
})
