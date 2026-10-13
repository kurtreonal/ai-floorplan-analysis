import { describe, expect, it } from 'vitest'
import { connectTouchingWireEndpoints, detachDevice, findDeviceWireSnap, moveConnectedDevice, findWireDeviceSnap, moveConnectedWirePoint } from './deviceConnections.js'

const symbol = {id:'symbol-0001', center:{x:10,y:10}, disposition:'unresolved'}
const draft = {symbols:[symbol], wirings:[{id:'segment-0001', disposition:'unresolved',
  points:[{x:30,y:10},{x:90,y:10}], installation_method:'concealed_in_ceiling'}]}

describe('explicit device attachments', () => {
  it('requires intentional detachment before bridging independent runs and rejects a collapsed segment', () => {
    const attached=moveConnectedDevice(draft,symbol,findDeviceWireSnap({x:30,y:10},symbol.id,draft.wirings,5))
    const wires=[...attached.wirings,{id:'segment-0002',disposition:'unresolved',points:[{x:200,y:10},{x:250,y:10}]}]
    expect(findDeviceWireSnap({x:200,y:10},symbol.id,wires,5)).toBeNull()
    expect(moveConnectedDevice(attached,{...symbol,center:{x:90,y:10}})).toBe(attached)
  })
  it('does not attach on placement, proximity or an interior crossing', () => {
    const next = moveConnectedDevice(draft,{...symbol,center:{x:31,y:10}})
    expect(next.wirings).toEqual(draft.wirings)
    expect(findDeviceWireSnap({x:50,y:10},symbol.id,draft.wirings,5)).toBeNull()
  })
  it('commits, moves, serializes and detaches without duplicate paths', () => {
    const snap = findDeviceWireSnap({x:29,y:10},symbol.id,draft.wirings,5)
    const attached = moveConnectedDevice(draft,symbol,snap)
    expect(attached.wirings[0].device_attachments).toEqual([{symbol_id:symbol.id,point_index:0}])
    const moved = moveConnectedDevice(JSON.parse(JSON.stringify(attached)),{...symbol,center:{x:40,y:20}})
    expect(moved.wirings[0].points[0]).toEqual({x:40,y:20})
    expect(moved.wirings).toHaveLength(1)
    const detached = detachDevice(moved,symbol.id)
    expect(moveConnectedDevice(detached,{...symbol,center:{x:60,y:20}}).wirings).toEqual(detached.wirings)
    expect(draft.wirings[0].points[0]).toEqual({x:30,y:10})
  })
  it('rejects ambiguous independent endpoints and endpoints occupied by other devices', () => {
    expect(findDeviceWireSnap({x:30,y:10},symbol.id,[...draft.wirings,{...draft.wirings[0],id:'segment-0002'}],5)).toBeNull()
    expect(findDeviceWireSnap({x:30,y:10},symbol.id,[{...draft.wirings[0],device_attachments:[{symbol_id:'symbol-0002',point_index:0}]}],5)).toBeNull()
  })
})

describe('wire endpoint magnets', () => {
  it('moves only the wire, preserves fractional device anchors and metadata, then follows device movement', () => {
    const source = {...draft, symbols:[{...symbol,center:{x:10.125,y:10.875}}]}
    const before = structuredClone(source)
    const snap = findWireDeviceSnap({x:12,y:11},'segment-0001',0,source,{},14)
    const attached = moveConnectedWirePoint(source,'segment-0001',0,{x:12,y:11},400,300,snap)
    expect(attached.symbols).toEqual(source.symbols)
    expect(attached.wirings[0].points[0]).toEqual(source.symbols[0].center)
    expect(attached.wirings[0].device_attachments).toEqual([{symbol_id:symbol.id,point_index:0}])
    expect(attached.wirings[0].installation_method).toBe('concealed_in_ceiling')
    expect(attached.wirings).toHaveLength(1)
    const moved = moveConnectedDevice(JSON.parse(JSON.stringify(attached)),{...source.symbols[0],center:{x:22.5,y:30.75}})
    expect(moved.wirings[0].points[0]).toEqual({x:22.5,y:30.75})
    expect(source).toEqual(before)
  })
  it('attaches either endpoint, but not interior points or mere proximity', () => {
    const source = {...draft, wirings:[{...draft.wirings[0],points:[{x:30,y:10},{x:50,y:10},{x:90,y:10}]}]}
    expect(findWireDeviceSnap(symbol.center,'segment-0001',1,source,{},14)).toBeNull()
    for (const index of [0,2]) expect(findWireDeviceSnap(symbol.center,'segment-0001',index,source,{},14)?.symbolId).toBe(symbol.id)
    const free = moveConnectedWirePoint(source,'segment-0001',0,{x:11,y:10},400,300)
    expect(free.wirings[0].device_attachments).toEqual([])
  })
  it('excludes annotations, rejected devices, ambiguous targets, collapsed paths and unrelated connected runs', () => {
    expect(findWireDeviceSnap(symbol.center,'segment-0001',0,draft,{[symbol.id]:{family:'annotation'}},14)).toBeNull()
    expect(findWireDeviceSnap(symbol.center,'segment-0001',0,{...draft,symbols:[{...symbol,disposition:'rejected'}]}, {},14)).toBeNull()
    expect(findWireDeviceSnap(symbol.center,'segment-0001',0,{...draft,symbols:[symbol,{...symbol,id:'symbol-0002'}]}, {},14)).toBeNull()
    expect(findWireDeviceSnap({x:90,y:10},'segment-0001',0,{...draft,symbols:[{...symbol,center:{x:90,y:10}}]}, {},14)).toBeNull()
    const other = {...draft.wirings[0],id:'segment-0002',circuit_id:2,device_attachments:[{symbol_id:symbol.id,point_index:0}]}
    expect(findWireDeviceSnap(symbol.center,'segment-0001',0,{...draft,wirings:[{...draft.wirings[0],circuit_id:1},other]}, {},14)).toBeNull()
  })
  it('revalidates stale previews and supports explicit drag-away detachment', () => {
    const snap = findWireDeviceSnap(symbol.center,'segment-0001',0,draft,{},14)
    const stale = {...draft,symbols:[{...symbol,center:{x:15,y:10}}]}
    expect(moveConnectedWirePoint(stale,'segment-0001',0,symbol.center,400,300,snap)).toBe(stale)
    const attached = moveConnectedWirePoint(draft,'segment-0001',0,symbol.center,400,300,snap)
    const detached = moveConnectedWirePoint(attached,'segment-0001',0,{x:40,y:30},400,300)
    expect(detached.wirings[0].device_attachments).toEqual([])
    expect(detached.symbols[0].center).toEqual(symbol.center)
  })
  it('uses a projected screen-distance callback in 3D rather than an arbitrary world radius', () => {
    const distance = () => 13
    expect(findWireDeviceSnap({x:390,y:290},'segment-0001',0,draft,{},16,distance)?.symbolId).toBe(symbol.id)
    expect(findWireDeviceSnap(symbol.center,'segment-0001',0,draft,{},16,() => 17)).toBeNull()
  })
})

describe('automatic endpoint contacts shared by both views', () => {
  const presentation = {[symbol.id]:{family:'switch',sourceBounds:{x:0,y:0,width:20,height:20}}}
  it('connects port contacts, preserves origins and supports persisted intentional detachment', () => {
    const source = {...draft,wirings:[{...draft.wirings[0],points:[{x:19,y:10},{x:90,y:10}]},
      {...draft.wirings[0],id:'segment-0002',points:[{x:0,y:10},{x:1,y:10}]}]}
    const before=structuredClone(source)
    const connected=connectTouchingWireEndpoints(source,presentation)
    expect(connected.wirings.every(w => w.device_attachments?.length === 1)).toBe(true)
    expect(connected.wirings[0].points[0]).toEqual(symbol.center)
    expect(connectTouchingWireEndpoints(connected,presentation)).toBe(connected)
    const detached=JSON.parse(JSON.stringify(detachDevice(connected,symbol.id)))
    expect(connectTouchingWireEndpoints(detached,presentation)).toBe(detached)
    expect(source).toEqual(before)
  })
  it('does not turn nearby grid tips, crossings or ambiguous devices into connections', () => {
    const grid={...draft,wirings:[{...draft.wirings[0],points:[{x:19,y:19},{x:90,y:19}]}]}
    expect(connectTouchingWireEndpoints(grid,presentation)).toBe(grid)
    const crossing={...draft,wirings:[{...draft.wirings[0],points:[{x:0,y:10},symbol.center,{x:90,y:10}]}]}
    // First endpoint contacts the glyph at the edge; the interior point never attaches.
    expect(connectTouchingWireEndpoints(crossing,{})).toBe(crossing)
    const ambiguous={...draft,symbols:[symbol,{...symbol,id:'symbol-0002'}],wirings:[{...draft.wirings[0],points:[symbol.center,{x:90,y:10}]}]}
    expect(connectTouchingWireEndpoints(ambiguous,{})).toBe(ambiguous)
  })
})
