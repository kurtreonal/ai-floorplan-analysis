import {expect,it} from 'vitest'
import {devicePlacement} from './devicePlacement.js'
import {buildDraftRoomScene} from '../detection-review/draftRoomScene.js'

it('uses guidance relative to each floor and lets stored installation heights override the planning preset',()=>{
  const scene={width:10,depth:10,elevation:6,ceilingElevation:9,walls:[],planningMountingHeights:{outlet:.45,switch:1.2}}
  const symbol={position:[2,6,2]}
  expect(devicePlacement(symbol,scene,'outlet').position[1]).toBe(6.45)
  expect(devicePlacement(symbol,scene,'switch').position[1]).toBe(7.2)
  expect(devicePlacement({...symbol,installation:{provenance:'designer_supplied_planning',elevation_meters:6.8,wall_id:null}},scene,'outlet').position[1]).toBe(6.8)
})

it('labels an assumed under-floor connection as illustrative and keeps elevations out of saved draft data',()=>{
  const draft={walls:[],rooms:[],symbols:[{id:'s',center:{x:20,y:20}}],wirings:[{id:'w',source_evidence_required:true,
    points:[{x:20,y:20},{x:60,y:20}],installation_method:'concealed_under_floor',device_attachments:[{symbol_id:'s',point_index:0}]}]}
  const before=structuredClone(draft)
  const unresolved=buildDraftRoomScene(draft,100,100,.75,{s:{family:'outlet'}})
  expect(unresolved.draftWires[0].unmeasuredDeviceIds).toEqual(['s'])
  expect(unresolved.draftWires[0].segments.some(s => s.previewDrop)).toBe(false)
  const guided=buildDraftRoomScene(draft,100,100,.75,{s:{family:'outlet'}},{planningMountingHeights:{outlet:.45,switch:1.2}})
  const rise=guided.draftWires[0].segments.find(s => s.previewDrop)
  expect(rise.illustrative).toBe(true)
  expect(rise.end[1]-rise.start[1]).toBeCloseTo(.45*guided.unitsPerMeter)
  expect(draft).toEqual(before)
})
