import {expect,it} from 'vitest'
import {withMountingDefaults} from './deviceMounting.js'
import {deviceClipboardSnapshot} from './useDeviceClipboard.js'
import {reviewGeometryPayload} from './devicePresentation.js'
import {buildDraftRoomScene} from './draftRoomScene.js'
import {devicePlacement,deviceConnector} from '../viewer-3d/devicePlacement.js'

it('applies only mapped backend VED defaults and preserves overrides and references',()=>{
  const defaults={outlet:.3,switch:1.2},presentation={mapped:true,name:'Convenience outlet'}
  expect(withMountingDefaults({},presentation,defaults)).toMatchObject({mounting_height_meters:.3,mounting_reference:'device_center',mounting_height_source:'ved_default'})
  for(const original of [{mounting_height_meters:.8},{mounting_height_meters:.8,mounting_reference:'box_bottom'}])expect(withMountingDefaults(original,presentation,defaults)).toEqual(original)
  expect(withMountingDefaults({}, {...presentation,mapped:false},defaults)).toEqual({})
  expect(withMountingDefaults({}, {...presentation,name:'Data outlet'},defaults)).toEqual({})
  const previous={mounting_height_meters:.3,mounting_reference:'device_center',mounting_height_source:'ved_default'}
  expect(withMountingDefaults(previous,{mapped:true,name:'Wall switch'},defaults).mounting_height_meters).toBe(1.2)
})
it('preserves center and separate terminal offset through payload, copy and synchronized 3D placement',()=>{
  const symbol={id:'s',center:{x:20,y:30},disposition:'added',symbol_legend_id:1,mounting_height_meters:.3,mounting_reference:'device_center',terminal_offset_meters:.1,mounting_height_source:'designer'}
  const draft={symbols:[symbol],walls:[],rooms:[],wirings:[]}
  expect(reviewGeometryPayload(draft).symbols[0]).toMatchObject({mounting_reference:'device_center',terminal_offset_meters:.1})
  expect(deviceClipboardSnapshot(symbol)).toMatchObject({mounting_reference:'device_center',terminal_offset_meters:.1})
  const scene=buildDraftRoomScene(draft,100,100,.75,{s:{family:'outlet'}})
  const placement=devicePlacement(scene.symbols[0],scene,'outlet')
  expect(placement.position[1]).toBeCloseTo(.3*scene.unitsPerMeter)
  expect(deviceConnector(placement)[1]).toBeCloseTo(.4*scene.unitsPerMeter)
})
