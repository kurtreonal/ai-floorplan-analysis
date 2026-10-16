import { describe,it,expect } from 'vitest'
import { findWireEndpointSnap } from './wirePathSnap.js'
import { moveConnectedWirePoint } from './deviceConnections.js'
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
})
