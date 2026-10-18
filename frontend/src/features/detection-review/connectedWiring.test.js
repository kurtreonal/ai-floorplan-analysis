import { expect, it } from 'vitest'
import { appendDrawingVertex, commitWiringPath, wiringComponents } from './connectedWiring.js'
import { connectedWireIds, updateWireNetwork, insertWireVertex, deleteWireVertex } from './wireJunctions.js'
import { moveConnectedDevice, moveConnectedWirePoint } from './deviceConnections.js'
import { wiringSavePayload, initialWiringDraft } from './observedWiringDraft.js'
import { draftWiringScene } from './draftWiringScene.js'

const p=(x,y)=>({x,y}), v=(x,y,snap=null)=>({point:p(x,y),snap})
const blank=()=>({symbols:[],wirings:[]})
const snap=(id,x,y)=>({id,x,y,kind:'wire',snapped:true})
const length=wires=>wires.reduce((total,w)=>total+w.points.slice(1).reduce((n,b,i)=>n+Math.hypot(b.x-w.points[i].x,b.y-w.points[i].y),0),0)

it('draws three connected segments in one path; ignores zero-length/duplicate spans but permits an intentional loop',()=>{
  let vertices=[]
  for(const [x,y] of [[0,0],[30,0],[30,30],[0,30],[0,0]])vertices=appendDrawingVertex(vertices,p(x,y))
  expect(appendDrawingVertex(vertices,p(0,0))).toBe(vertices)
  const draft=commitWiringPath(blank(),vertices,{})
  expect(draft.wirings).toHaveLength(1)
  expect(draft.wirings[0].points).toHaveLength(5)
  expect(draft.wirings[0].vertex_ids[0]).toBe(draft.wirings[0].vertex_ids[4])
  const moved=moveConnectedWirePoint(draft,draft.wirings[0].id,0,p(2,2),100,100)
  expect(moved.wirings[0].points[4]).toEqual(p(2,2))
  const line=[v(0,0),v(30,0)]
  expect(appendDrawingVertex(line,p(0,0))).toBe(line)
})

it('extends a second session, splits a T without adding connecting length, preserves lineage and moves every incident arm',()=>{
  const first=commitWiringPath(blank(),[v(0,20),v(100,20)],{})
  const before=structuredClone(first), id=first.wirings[0].id
  const joined=commitWiringPath(first,[v(50,20,snap(id,50,20)),v(50,60)],{})
  expect(first).toEqual(before)
  expect(joined.wirings[0].id).toBe(id)
  expect(joined.wirings[0].points).toHaveLength(3)
  expect(joined.wirings[0].vertex_ids[2]).toBe(first.wirings[0].vertex_ids[1])
  expect(length(joined.wirings)).toBe(140)
  expect(connectedWireIds(joined,id).size).toBe(2)
  const moved=moveConnectedWirePoint(joined,id,1,p(60,20),200,200)
  expect(moved.wirings[1].points[0]).toEqual(p(60,20))
  const removed=updateWireNetwork(joined,{...joined.wirings[1],disposition:'rejected'})
  expect(connectedWireIds(removed,id).size).toBe(1)
  expect(removed.wirings[0].network_lineage).toContain(joined.wirings[1].id)
  expect(removed.wirings[0].points).toEqual(joined.wirings[0].points)
})

it('does not join a crossing, incompatible circuit or old unspecified device terminals',()=>{
  const first=commitWiringPath(blank(),[v(0,20),v(100,20)],{circuit_id:'C1'})
  const crossing=commitWiringPath(first,[v(50,0),v(50,40)],{})
  expect(new Set(wiringComponents(crossing.wirings).values()).size).toBe(2)
  expect(()=>commitWiringPath(first,[v(100,20,snap(first.wirings[0].id,100,20)),v(140,20)],{circuit_id:'C2'})).toThrow(/different circuits/)
  const old=[{id:'a',points:[p(0,0),p(30,0)],device_attachments:[{symbol_id:'s',point_index:1}]},
    {id:'b',points:[p(30,0),p(60,0)],device_attachments:[{symbol_id:'s',point_index:0}]}]
  expect(new Set(wiringComponents(old).values()).size).toBe(2)
})

it('connects only the explicitly selected terminal, survives JSON persistence and projects identical 3D networks',()=>{
  const draft={...blank(),symbols:[{id:'symbol-0001',center:p(30,20)}]}
  const ds={kind:'device',snapped:true,id:'symbol-0001',x:30,y:20,terminalId:'A'}
  const first=commitWiringPath(draft,[v(0,20),v(30,20,ds)],{})
  const second=commitWiringPath(first,[v(30,20,ds),v(60,20)],{})
  const distinct=commitWiringPath(second,[v(30,20,{...ds,terminalId:'B'}),v(30,50)],{})
  expect(connectedWireIds(distinct,first.wirings[0].id).size).toBe(2)
  const record={review:JSON.parse(JSON.stringify(wiringSavePayload(distinct.wirings)))}
  const reloaded={...distinct,wirings:initialWiringDraft(record)}
  expect(reloaded.wirings).toEqual(distinct.wirings)
  const projected=draftWiringScene(reloaded.wirings,{sourceScale:1,width:100,depth:100,ceilingElevation:3,symbols:[]})
  expect(projected.map(w=>w.networkId)).toEqual([...wiringComponents(reloaded.wirings).values()])
  expect(projected[0].points.map(([x,,y])=>p(x,y))).toEqual(first.wirings[0].points)
  const moved=moveConnectedDevice(reloaded,{...draft.symbols[0],center:p(35,25)})
  expect(moved.wirings[0].points.at(-1)).toEqual(p(35,25))
  expect(moved.wirings[1].points[0]).toEqual(p(35,25))
  expect(moved.wirings).toHaveLength(3)
})

it('reprojects two interior snaps against the updated edge without losing source attributes',()=>{
  const original={id:'segment-0001',points:[p(0,20),p(100,20)],line_style:'dashed',source_evidence_required:true}
  const result=commitWiringPath({symbols:[],wirings:[original]},[
    v(20,20,snap(original.id,20,20)),v(20,50),v(80,50),v(80,20,snap(original.id,80,20))],{})
  expect(result.wirings[0]).toMatchObject({id:original.id,line_style:'dashed',source_evidence_required:true})
  expect(length([result.wirings[0]])).toBe(100)
  expect(connectedWireIds(result,original.id).size).toBe(2)
})

it('keeps the repeated loop node coincident when its device or an incident branch moves',()=>{
  const device={id:'symbol-0001',center:p(20,20)}
  const ds={kind:'device',snapped:true,id:device.id,x:20,y:20}
  const loop=commitWiringPath({symbols:[device],wirings:[]},[v(20,20,ds),v(80,20),v(80,80),v(20,20)],{})
  const moved=moveConnectedDevice(loop,{...device,center:p(25,25)})
  expect(moved.wirings[0].points[0]).toEqual(p(25,25))
  expect(moved.wirings[0].points.at(-1)).toEqual(p(25,25))
  const bare=commitWiringPath(blank(),[v(20,20),v(80,20),v(80,80),v(20,20)],{})
  const joined=commitWiringPath(bare,[v(20,20,snap(bare.wirings[0].id,20,20)),v(10,20)],{})
  const result=moveConnectedWirePoint(joined,joined.wirings[1].id,0,p(25,25),100,100)
  expect(result.wirings[0].points[0]).toEqual(p(25,25))
  expect(result.wirings[0].points.at(-1)).toEqual(p(25,25))
})

it('never reuses a deleted vertex identity after a saved reload',()=>{
  const first=commitWiringPath(blank(),[v(0,20),v(100,20)],{})
  const id=first.wirings[0].id
  const inserted=insertWireVertex(first,id,0,.5)
  const old=inserted.wirings[0].vertex_ids[1]
  const removed=JSON.parse(JSON.stringify(deleteWireVertex(inserted,id,1)))
  const again=insertWireVertex(removed,id,0,.6)
  expect(again.wirings[0].vertex_ids[1]).not.toBe(old)
  expect(again.wirings[0].vertex_ids[0]).toBe(first.wirings[0].vertex_ids[0])
})
