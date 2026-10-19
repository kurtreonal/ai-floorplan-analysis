import { describe,it,expect } from 'vitest'
import { findWireEndpointSnap, findWireEndpointTargets } from './wirePathSnap.js'
import { moveConnectedWirePoint } from './deviceConnections.js'
import { wiringComponents } from './connectedWiring.js'
const path = (id,points,extra={}) => ({id,points:points.map(([x,y])=>({x,y})),disposition:'unresolved',device_attachments:[],...extra})
const fixture = () => ({symbols:[],wirings:[path('segment-0001',[[0,0],[8,8]]),path('segment-0002',[[10,0],[10,20]])]})
describe('direct endpoint path magnet',()=>{
  it('previews without mutation, commits a split and shared node once',()=>{
    const draft=fixture(),before=structuredClone(draft)
    const snap=findWireEndpointSnap({x:9,y:9},'segment-0001',1,draft,{},2)
    expect(snap).toMatchObject({kind:'junction',point:{x:10,y:9},t:.45})
    expect(draft).toEqual(before)
    const next=moveConnectedWirePoint(draft,'segment-0001',1,snap.point,100,100,snap)
    expect(next.wirings[1].points).toHaveLength(3)
    expect(next.wirings[0].junction_attachments[0].junction_id).toBe(next.wirings[1].junction_attachments[0].junction_id)
    expect(findWireEndpointSnap(snap.point,'segment-0001',1,next,{},2)).toBeNull()
  })
  it('does not snap crossings, incompatible circuits, generated/observed or ambiguous paths',()=>{
    const draft=fixture()
    draft.wirings[0].points.splice(1,0,{x:2,y:2})
    expect(findWireEndpointSnap({x:10,y:10},'segment-0001',1,draft,{},3)).toBeNull()
    for(const extra of [{circuit_id:'other'},{origin:'generated'},{elevation_meters:3}]) {
      const d=fixture();Object.assign(d.wirings[1],extra)
      expect(findWireEndpointSnap({x:10,y:10},'segment-0001',1,d,{},3)).toBeNull()
    }
    const d=fixture();d.wirings.push(path('segment-0003',[[10,0],[10,20]]))
    expect(findWireEndpointSnap({x:10,y:10},'segment-0001',1,d,{},3)).toBeNull()
  })
  it('uses projected distance for 3D and revalidates stale preview metadata',()=>{
    const d=fixture(),snap=findWireEndpointSnap({x:9,y:9},'segment-0001',1,d,{},16,null,()=>3)
    expect(snap.kind).toBe('junction')
    d.wirings[1].circuit_id='changed'
    expect(()=>moveConnectedWirePoint(d,'segment-0001',1,snap.point,100,100,snap)).toThrow(/Circuit/)
  })
  it('offers distinct overlapping devices without automatically connecting any',()=>{
    const d=fixture()
    d.symbols=['device-1','device-2'].map(id=>({id,center:{x:4,y:4}}))
    const before=structuredClone(d)
    const choices=findWireEndpointTargets({x:4,y:4},'segment-0001',0,d,{},1)
    expect(choices.map(c=>[c.symbolId,c.terminalId])).toEqual([['device-1','design-anchor'],['device-2','design-anchor']])
    expect(findWireEndpointSnap({x:4,y:4},'segment-0001',0,d,{},1)).toBeNull()
    expect(d).toEqual(before)
    const next=moveConnectedWirePoint(d,'segment-0001',0,choices[1].point,100,100,choices[1])
    expect(next.wirings[0].device_attachments).toEqual([{symbol_id:'device-2',point_index:0,terminal_id:'design-anchor'}])
    expect(next.symbols).toEqual(d.symbols)
    expect(next.wirings).toHaveLength(2)
    const stale={...d,symbols:d.symbols.filter(s=>s.id!=='device-2')}
    expect(moveConnectedWirePoint(stale,'segment-0001',0,choices[1].point,100,100,choices[1])).toBe(stale)
  })
  it('keeps co-located explicit terminals distinct through commit and serialization',()=>{
    const d=fixture()
    d.symbols=[{id:'device-1',center:{x:4,y:4}}]
    for(const terminal of ['port-a','port-b'])d.wirings.push(path(terminal,[[4,4],[4,0]],{device_attachments:[{symbol_id:'device-1',point_index:0,terminal_id:terminal}]}))
    const choices=findWireEndpointTargets({x:4,y:4},'segment-0001',0,d,{},1)
    expect(choices.map(c=>c.terminalId)).toEqual(['port-a','port-b'])
    const next=moveConnectedWirePoint(d,'segment-0001',0,choices[1].point,100,100,choices[1])
    expect(JSON.parse(JSON.stringify(next)).wirings[0].device_attachments[0].terminal_id).toBe('port-b')
    const incompatible=structuredClone(d)
    incompatible.wirings.at(-1).circuit_id='other'
    expect(findWireEndpointTargets({x:4,y:4},'segment-0001',0,{...incompatible,wirings:incompatible.wirings.map(w=>w.id==='segment-0001'?{...w,circuit_id:'mine'}:w)},{},1)).toEqual([])
  })
  it('does not offer unsupported off-center terminal geometry that the save contract rejects',()=>{
    const d=fixture()
    d.symbols=[{id:'device-1',center:{x:4,y:4}}]
    d.wirings.push(path('port-a',[[3,4],[3,0]],{device_attachments:[{symbol_id:'device-1',point_index:0,terminal_id:'port-a'}]}),
      path('port-b',[[5,4],[5,0]],{device_attachments:[{symbol_id:'device-1',point_index:0,terminal_id:'port-b'}]}))
    expect(findWireEndpointTargets({x:4,y:4},'segment-0001',0,d,{},2)).toEqual([])
  })
  it('connects overlapping devices individually without merging their circuits by location',()=>{
    const d=fixture()
    d.symbols=['device-1','device-2'].map(id=>({id,center:{x:4,y:4}}))
    d.wirings[0].source_evidence_required=true
    const first=findWireEndpointTargets({x:4,y:4},'segment-0001',0,d,{},1).find(c=>c.symbolId==='device-1')
    const attached=moveConnectedWirePoint(d,'segment-0001',0,first.point,100,100,first)
    const second=findWireEndpointTargets({x:4,y:4},'segment-0002',0,attached,{},1).find(c=>c.symbolId==='device-2')
    const result=moveConnectedWirePoint(attached,'segment-0002',0,second.point,100,100,second)
    expect(result.wirings.map(w=>w.device_attachments[0].symbol_id)).toEqual(['device-1','device-2'])
    expect(new Set(wiringComponents(result.wirings).values()).size).toBe(2)
    expect(result.wirings[0].source_evidence_required).toBe(true)
    expect(result.wirings[0].disposition).toBe('corrected')
  })
})
