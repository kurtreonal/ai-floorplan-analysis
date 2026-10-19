import { describe,it,expect } from 'vitest'
import { drawingWorkPlane, sourcePointOnPlane, spatialDrawingTarget, drawingTargetVertex } from './workPlaneDrawing.js'
import { commitWiringPath } from '../detection-review/connectedWiring.js'
import { addConnectedWall } from '../detection-review/wallDrawing.js'
import { draftWiringScene } from '../detection-review/draftWiringScene.js'

const scene={sourceScale:.1,unitsPerMeter:1,width:20,depth:20}
const context={pixels_per_meter:10,floor_elevation_meters:12}
const settings={elevation:'14.8',thickness:'.2',height:'3',length:'',axis:'none'}
const blank=()=>({symbols:[],walls:[],wirings:[],openings:[]})
describe('explicit 3D work plane',()=>{
  it('requires real calibration, floor datum and explicit dimensions rather than preview defaults',()=>{
    expect(drawingWorkPlane('wire',settings,context,scene)).toMatchObject({elevation:14.8,sceneElevation:expect.closeTo(2.8)})
    for(const inputs of [{...context,pixels_per_meter:null},{...context,floor_elevation_meters:null}])expect(()=>drawingWorkPlane('wire',settings,inputs,scene)).toThrow(/scale and floor/)
    expect(()=>drawingWorkPlane('wire',{...settings,elevation:''},context,scene)).toThrow(/service elevation/)
    expect(()=>drawingWorkPlane('draw',{...settings,thickness:''},context,scene)).toThrow(/thickness/)
    expect(()=>drawingWorkPlane('wire',settings,context,{...scene,unitsPerMeter:.5})).toThrow(/calibrated source/)
    expect(drawingWorkPlane('draw',settings,context,scene)).toMatchObject({elevation:12,sceneElevation:0,thickness:.2,height:3})
  })
  it('maps actual oblique rays and rejects parallel/backwards/out-of-page intersections',()=>{
    const ray={origin:{x:1,y:10,z:2},direction:{x:.5,y:-1,z:1}}
    expect(sourcePointOnPlane(ray,2,scene)).toEqual({x:50,y:100})
    expect(sourcePointOnPlane({...ray,direction:{x:1,y:0,z:1}},2,scene)).toBeNull()
    expect(sourcePointOnPlane(ray,12,scene)).toBeNull()
    expect(sourcePointOnPlane(ray,-100,scene)).toBeNull()
    expect(sourcePointOnPlane({origin:{x:2,y:-2,z:3},direction:{x:0,y:1,z:0}},0,scene)).toEqual({x:20,y:30})
  })
  it('keeps angled exact wall lengths and configured axis constraints',()=>{
    const draft=blank(),config=drawingWorkPlane('draw',{...settings,length:'5'},context,scene)
    const vertices=[{point:{x:0,y:0}}]
    const target=spatialDrawingTarget({x:3,y:4},{tool:'draw',vertices,draft,config,snapping:false})
    expect(target.point).toEqual({x:30,y:40})
    const next=addConnectedWall(draft,{start:vertices[0].point,end:target.point,thickness_meters:config.thickness,height_meters:config.height})
    expect(Math.hypot(next.walls[0].end.x,next.walls[0].end.y)/config.ppm).toBe(5)
    const locked=spatialDrawingTarget({x:20,y:30},{tool:'draw',vertices,draft,config:{...config,axis:'x'},snapping:false})
    expect(locked.point).toEqual({x:50,y:0})
  })
  it('splits only an intentional compatible path snap and retains explicit elevation through projection',()=>{
    const draft=blank(),config=drawingWorkPlane('wire',settings,context,scene)
    draft.wirings=[{id:'segment-0001',points:[{x:20,y:40},{x:100,y:40}],elevation_meters:14.8,installation_method:'concealed_in_ceiling'}]
    const target=spatialDrawingTarget({x:60,y:41},{tool:'wire',vertices:[],draft,config,method:'concealed_in_ceiling'})
    expect(target.snap).toMatchObject({kind:'wire',id:'segment-0001',x:60,y:40})
    const next=commitWiringPath(draft,[{point:target.point,snap:target.snap},{point:{x:60,y:80}}],{elevation_meters:config.elevation,installation_method:'concealed_in_ceiling'})
    expect(next.wirings[0].points).toHaveLength(3)
    const projected=draftWiringScene(JSON.parse(JSON.stringify(next.wirings)),{...scene,ceilingElevation:99,floorElevationMeters:12,symbols:[]})
    expect(projected.every(w=>w.points.every(p=>Math.abs(p[1]-2.8)<1e-8))).toBe(true)
    expect(projected[0].networkId).toBe(projected[1].networkId)
    const wrong=spatialDrawingTarget({x:60,y:41},{tool:'wire',vertices:[],draft,config:{...config,elevation:15},method:'concealed_in_ceiling'})
    expect(wrong.snap).toBeUndefined()
  })
  it('offers overlapping terminal identities without connecting all, and rejects incompatible shared terminals',()=>{
    const draft=blank(),config=drawingWorkPlane('wire',settings,context,scene)
    draft.symbols=['symbol-0001','symbol-0002'].map(id=>({id,center:{x:50,y:50}}))
    const options={tool:'wire',vertices:[],draft,config,method:'concealed_in_ceiling'}
    const target=spatialDrawingTarget({x:50,y:50},options)
    expect(target.choices).toHaveLength(2)
    expect(target.snap).toBeUndefined()
    const chosen=drawingTargetVertex(target.choices[1])
    const next=commitWiringPath(draft,[chosen,{point:{x:100,y:50}}],{elevation_meters:config.elevation,installation_method:'concealed_in_ceiling'})
    expect(next.wirings[0].device_attachments).toEqual([{symbol_id:'symbol-0002',terminal_id:'design-anchor',point_index:0}])
    const blocked=spatialDrawingTarget({x:50,y:50},{...options,draft:next,config:{...config,elevation:20}})
    expect(blocked.choices.map(c=>c.symbolId)).not.toContain('symbol-0002')
  })
})
