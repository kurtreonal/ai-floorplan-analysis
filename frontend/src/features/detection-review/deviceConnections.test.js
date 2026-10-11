import { describe, expect, it } from 'vitest'
import { detachDevice, findDeviceWireSnap, moveConnectedDevice } from './deviceConnections.js'

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
