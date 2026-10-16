import { describe, expect, it } from 'vitest'
import { connectedWireIds, deleteWireVertex, detachWireJunction, insertWireVertex, joinWireJunction, updateWireNetwork } from './wireJunctions.js'
import { moveConnectedWirePoint, findWireDeviceSnap, connectTouchingWireEndpoints } from './deviceConnections.js'

function fixture() {
  return {symbols:[],wirings:[
    {id:'segment-0001',disposition:'unresolved',circuit_id:'C1',elevation_meters:null,points:[{x:0,y:20},{x:100,y:20}]},
    {id:'segment-0002',disposition:'unresolved',circuit_id:'C1',elevation_meters:null,points:[{x:50,y:70},{x:50,y:120}]},
  ]}
}

describe('explicit wire junction graph',()=>{
  it('splits a T junction, moves all incident vertices, survives reload and detaches without another path',()=>{
    const draft=fixture(), before=structuredClone(draft)
    const joined=joinWireJunction(draft,'segment-0002',0,'segment-0001',0,.5)
    expect(joined.wirings[0].points).toEqual([{x:0,y:20},{x:50,y:20},{x:100,y:20}])
    expect(joined.wirings[1].points[0]).toEqual({x:50,y:20})
    expect(joined.wirings[0].junction_attachments).toEqual([{junction_id:'junction-0001',point_index:1}])
    const reloaded=JSON.parse(JSON.stringify(joined))
    const moved=moveConnectedWirePoint(reloaded,'segment-0002',0,{x:60,y:30},200,200)
    expect(moved.wirings[0].points[1]).toEqual({x:60,y:30})
    expect(moved.wirings[1].points[0]).toEqual({x:60,y:30})
    expect(moved.wirings).toHaveLength(2)
    const detached=detachWireJunction(moved,'segment-0002',0)
    expect(detached.wirings.every(w=>!w.junction_attachments.length)).toBe(true)
    expect(moveConnectedWirePoint(detached,'segment-0002',0,{x:80,y:40},200,200).wirings[0]).toEqual(detached.wirings[0])
    expect(draft).toEqual(before)
  })
  it('keeps crossings disconnected until explicit commitment, including L/X and angled joins',()=>{
    const draft=fixture()
    draft.wirings[1].points=[{x:50,y:0},{x:50,y:20},{x:50,y:40}]
    expect(connectedWireIds(draft,'segment-0001').size).toBe(1)
    const joined=joinWireJunction(draft,'segment-0002',1,'segment-0001',0,.5)
    expect(connectedWireIds(joined,'segment-0001').size).toBe(2)
    const angled=fixture();angled.wirings[0].points=[{x:10,y:10},{x:70,y:40}]
    const l=joinWireJunction(angled,'segment-0002',0,'segment-0001',0,1)
    expect(l.wirings[1].points[0]).toEqual({x:70,y:40})
    expect(l.wirings[0].points).toHaveLength(2)
  })
  it('reindexes evidence-supported device attachments on insert/delete without moving them',()=>{
    const draft=fixture()
    draft.wirings[0].device_attachments=[{symbol_id:'symbol-0001',point_index:1,provenance:'source_supported_proposal',source_connection_id:'connection-0001'}]
    const inserted=insertWireVertex(draft,'segment-0001',0)
    expect(inserted.wirings[0].device_attachments[0]).toMatchObject({point_index:2,source_connection_id:'connection-0001'})
    expect(deleteWireVertex(inserted,'segment-0001',1).wirings[0].device_attachments[0].point_index).toBe(1)
    expect(()=>deleteWireVertex(inserted,'segment-0001',2)).toThrow(/Disconnect/)
  })
  it.each(['circuit_id','elevation_meters','installation_method'])('refuses conflicting %s and never modifies source on failure',key=>{
    const draft=fixture(), before=structuredClone(draft)
    draft.wirings[1][key]=key==='elevation_meters'?3:'different'
    expect(()=>joinWireJunction(draft,'segment-0002',0,'segment-0001',0,.5)).toThrow(/must match/)
    expect(draft.wirings[0]).toEqual(before.wirings[0])
  })
  it('preserves joined identity through network property changes and removes orphan references on deletion',()=>{
    const draft=joinWireJunction(fixture(),'segment-0002',0,'segment-0001',0,.5)
    const updated=updateWireNetwork(draft,{...draft.wirings[0],circuit_id:'C2',elevation_meters:3})
    expect(updated.wirings.every(w=>w.circuit_id==='C2' && w.elevation_meters===3)).toBe(true)
    const deleted=updateWireNetwork(updated,{...updated.wirings[1],disposition:'rejected'})
    expect(deleted.wirings[0].junction_attachments).toEqual([])
    expect(deleted.wirings[1].disposition).toBe('rejected')
    expect(()=>deleteWireVertex(draft,'segment-0001',1)).toThrow(/Disconnect/)
    expect(moveConnectedWirePoint(draft,'segment-0001',1,{x:0,y:20},200,200)).toBe(draft)
    expect(()=>moveConnectedWirePoint(draft,'segment-0002',0,{x:0,y:20},200,200)).toThrow(/collapse/)
  })
  it('does not auto-bind junctions to device terminals or accept device-occupied joins',()=>{
    const draft=fixture()
    const joined=joinWireJunction(draft,'segment-0002',0,'segment-0001',0,.5)
    joined.symbols=[{id:'symbol-0001',center:{x:50,y:20}}]
    expect(findWireDeviceSnap({x:50,y:20},'segment-0002',0,joined)).toBeNull()
    expect(connectTouchingWireEndpoints(joined).wirings[1].device_attachments).toBeUndefined()
    draft.wirings[0].device_attachments=[{symbol_id:'symbol-0001',point_index:1}]
    expect(()=>joinWireJunction(draft,'segment-0002',0,'segment-0001',0,1)).toThrow(/device terminal/)
  })
})
