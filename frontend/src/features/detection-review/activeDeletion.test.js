import { expect, it } from 'vitest'
import { deleteConnectedWall } from './wallDrawing.js'
import { detachDevice } from './deviceConnections.js'
import { applyWireEdits } from './wireJunctions.js'
import { wiringComponents } from './connectedWiring.js'
import { buildDraftRoomScene } from './draftRoomScene.js'
import { initialWiringDraft } from './observedWiringDraft.js'

it('explicit wall deletion keeps mounted device positions, heights and wiring but clears the wall binding',()=>{
  const draft={walls:[{id:'wall-0001',disposition:'accepted',start:{x:0,y:20},end:{x:100,y:20}}],rooms:[],
    symbols:[{id:'symbol-0001',disposition:'added',center:{x:25,y:20},mounting_wall_id:'wall-0001',mounting_height_meters:1.2}],
    wirings:[{id:'segment-0001',disposition:'corrected',points:[{x:25,y:0},{x:25,y:20}],device_attachments:[{symbol_id:'symbol-0001',point_index:1}]}]}
  const before=structuredClone(draft)
  expect(()=>deleteConnectedWall(draft,'wall-0001')).toThrow(/Detach/)
  const next=deleteConnectedWall(draft,'wall-0001',{detachMounted:true})
  expect(next.symbols[0]).toEqual({...draft.symbols[0],mounting_wall_id:null})
  expect(next.wirings).toEqual(draft.wirings)
  const scene=buildDraftRoomScene(next,100,100,.6)
  expect(scene.walls).toHaveLength(0)
  expect(scene.symbols).toHaveLength(1)
  expect(draft).toEqual(before)
})

it('device deletion detaches only that device, preserves unrelated branches and marks affected generated proposals unresolved',()=>{
  const draft={symbols:[],wirings:[{id:'a',points:[{x:0,y:0},{x:10,y:0}],device_attachments:[{symbol_id:'s1',point_index:0},{symbol_id:'s2',point_index:1}]},
    {id:'b',origin:'generated',source_device_id:'s1',target_kind:'device',target_id:'s3',assignment_state:'assigned',points:[{x:0,y:0},{x:20,y:0}],device_attachments:[]}]}
  const next=detachDevice(draft,'s1')
  expect(next.wirings).toHaveLength(2)
  expect(next.wirings[0].device_attachments).toEqual([{symbol_id:'s2',point_index:1}])
  expect(next.wirings[0].auto_connect_disabled_endpoints).toContain(0)
  expect(next.wirings[1].assignment_state).toBe('unresolved')
  expect(next.wirings.map(w=>w.points)).toEqual(draft.wirings.map(w=>w.points))
})

it('numeric wire removal updates junction components without deleting surviving branches and tombstones survive reload',()=>{
  const point={x:10,y:0}, contact={junction_id:'junction-0001',point_index:0}
  const draft={symbols:[],wirings:['a','b','c'].map((id,i)=>({id,disposition:'corrected',points:[point,{x:10+i*10,y:20}],junction_attachments:[contact],device_attachments:[]}))}
  const next=applyWireEdits(draft,draft.wirings.map(w=>w.id==='b'?{...w,disposition:'rejected'}:w))
  expect(next.wirings).toHaveLength(3)
  expect(wiringComponents(next.wirings).size).toBe(2)
  expect(next.wirings.filter(w=>w.id!=='b').every(w=>w.junction_attachments.length===1)).toBe(true)
  const restored=initialWiringDraft({review:{observed_wiring:JSON.parse(JSON.stringify(next.wirings))},candidate:{payload:{observed_routes:{segments:[]}}}})
  expect(restored.find(w=>w.id==='b').disposition).toBe('rejected')
  const scene=buildDraftRoomScene({walls:[],rooms:[],symbols:[],wirings:restored},100,100,.6)
  expect(scene.draftWires.map(w=>w.id)).toEqual(['a','c'])
})
