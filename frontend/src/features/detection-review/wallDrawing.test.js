import {describe,it,expect} from 'vitest'
import {addConnectedWall,moveConnectedWall,deleteConnectedWall,resizeWall,wallPointerTarget,wallLength} from './wallDrawing.js'
import {wallMeasurements,formatWallMeasure} from './wallMeasurements.js'
import {buildWallTopology} from '../../geometry/wallTopology.js'
import {buildDraftRoomScene} from './draftRoomScene.js'
import {reviewGeometryPayload} from './devicePresentation.js'

const w=(id,start,end)=>({id,start,end,disposition:'accepted',estimated_thickness_pixels:10})
const p=(x,y)=>({x,y})
const draft=walls=>({walls,symbols:[],rooms:[],wirings:[],openings:[]})

describe('Blueprint3D interaction adapted to shared VED draft',()=>{
  it('draws and closes an exact rectangle without duplicate corners; computes interior rather than centerline labels',()=>{
    let d=draft([])
    for(const [a,b] of [[p(50,50),p(450,50)],[p(450,50),p(450,350)],[p(450,350),p(50,350)],[p(50,350),p(50,50)]])d=addConnectedWall(d,{start:a,end:b,estimated_thickness_pixels:10})
    expect(d.walls.map(wallLength)).toEqual([400,300,400,300])
    expect(new Set(d.walls.flatMap(w=>[JSON.stringify(w.start),JSON.stringify(w.end)])).size).toBe(4)
    const labels=wallMeasurements(d.walls)
    expect([...labels.values()].map(l=>l.length)).toEqual([390,290,390,290])
    expect([...labels.values()].every(l=>l.basis==='interior')).toBe(true)
    expect(buildWallTopology(d.walls.map(w=>({...w,thickness:10}))).junctions).toHaveLength(4)
  })
  it('retains a deliberately angled wall and aligns near-corner axes independent of zoom',()=>{
    const walls=[w('wall-0001',p(50,50),p(450,50))]
    expect(wallPointerTarget(p(200,53),walls,{scale:2}).point).toEqual(p(200,50))
    expect(wallPointerTarget(p(200,58),walls,{scale:2}).point).toEqual(p(200,58))
    expect(wallPointerTarget(p(203,205),walls,{scale:1,anchor:p(200,50)}).point).toEqual(p(200,205))
    expect(addConnectedWall(draft([]),{start:p(20,20),end:p(180,140)}).walls[0].end).toEqual(p(180,140))
  })
  it('splits an existing edge and retains its original identity and dimensions, remapping mounted devices',()=>{
    const source=draft([w('wall-0001',p(0,50),p(400,50))])
    source.symbols=[{id:'symbol-0001',center:p(350,50),mounting_wall_id:'wall-0001',disposition:'accepted'}]
    const before=structuredClone(source),next=addConnectedWall(source,{start:p(200,50),end:p(200,300)})
    expect(source).toEqual(before)
    expect(next.walls).toHaveLength(3)
    expect(next.walls[0]).toMatchObject({id:'wall-0001',end:p(200,50),estimated_thickness_pixels:10})
    expect(next.symbols[0].mounting_wall_id).toBe(next.walls[1].id)
    expect(next.walls[1].end).toEqual(p(400,50))
  })
  it('blocks collinear overlap/retrace, zero lengths and splitting through an opening',()=>{
    const d=draft([w('wall-0001',p(0,50),p(400,50))])
    expect(()=>addConnectedWall(d,{start:p(100,50),end:p(250,50)})).toThrow(/occupies/)
    expect(addConnectedWall(d,{start:p(5,5),end:p(5,5)})).toBe(d)
    d.openings=[{id:'opening-0001',disposition:'accepted',kind:'door',points:[p(150,50),p(250,50)]}]
    expect(()=>addConnectedWall(d,{start:p(200,50),end:p(200,300)})).toThrow(/opening/)
    expect(addConnectedWall(d,{start:p(150,50),end:p(150,300)}).openings).toEqual(d.openings)
  })
  it('numeric length anchors start and keeps connected corners, widths and height',()=>{
    const source=draft([w('wall-0001',p(10,10),p(110,10)),w('wall-0002',p(110,10),p(110,110))])
    source.walls[0].height_meters=2.5
    const resized=resizeWall(source.walls[0],200),next=moveConnectedWall(source,resized)
    expect(next.walls[0]).toMatchObject({start:p(10,10),end:p(210,10),height_meters:2.5,estimated_thickness_pixels:10})
    expect(next.walls[1].start).toEqual(p(210,10))
    expect(()=>resizeWall(source.walls[0],0)).toThrow()
    expect(reviewGeometryPayload(next).walls[0].height_meters).toBe(2.5)
  })
  it('moves explicitly mounted devices and the same connected wire; no duplicated route',()=>{
    const source=draft([w('wall-0001',p(0,50),p(400,50))])
    source.symbols=[{id:'symbol-0001',center:p(100,50),mounting_wall_id:'wall-0001',disposition:'accepted'}]
    source.wirings=[{id:'segment-0001',points:[p(100,0),p(100,50)],disposition:'accepted',device_attachments:[{symbol_id:'symbol-0001',point_index:1}]}]
    const next=moveConnectedWall(source,{...source.walls[0],start:p(0,80),end:p(400,80)})
    expect(next.symbols[0].center).toEqual(p(100,80))
    expect(next.wirings).toHaveLength(1)
    expect(next.wirings[0].points[1]).toEqual(p(100,80))
    expect(()=>deleteConnectedWall(next,'wall-0001')).toThrow(/Detach/)
  })
  it('preserves openings on movement; deletion is an undoable tombstone when unattached',()=>{
    const source=draft([w('wall-0001',p(0,50),p(400,50))])
    source.openings=[{id:'opening-0001',disposition:'accepted',points:[p(100,50),p(200,50)]}]
    const next=moveConnectedWall(source,{...source.walls[0],start:p(0,80),end:p(400,80)})
    expect(next.openings[0].points).toEqual([p(100,80),p(200,80)])
    expect(()=>deleteConnectedWall(next,'wall-0001')).toThrow()
    expect(deleteConnectedWall(draft(source.walls),'wall-0001').walls[0].disposition).toBe('rejected')
  })
  it('uses stored page scale and per-wall physical dimensions consistently in 3D',()=>{
    const d=draft([{...w('manual-wall-0001',p(100,100),p(500,100)),thickness_meters:.1,height_meters:2.5}])
    const scene=buildDraftRoomScene(d,1000,1000,.6,{}, {pixelsPerMeter:100})
    expect(scene.walls[0].size).toEqual([4,2.5,.1])
    expect(scene.unitsPerMeter).toBe(1)
    expect(formatWallMeasure(400,100)).toBe('4 m')
    expect(formatWallMeasure(400,100,'mm')).toBe('4000 mm')
    expect(formatWallMeasure(400,null)).toBe('400 px (unscaled)')
  })
  it('open walls are explicitly centerline measurements; unrelated detection records remain unchanged',()=>{
    const d=draft([w('wall-0001',p(0,50),p(400,50))])
    expect(wallMeasurements(d.walls).get('wall-0001')).toMatchObject({basis:'centerline',length:400})
    const next=addConnectedWall(d,{start:p(20,200),end:p(300,300)})
    expect(next.walls[0]).toBe(d.walls[0])
  })
  it('creates a shared editable X junction when a manually drawn wall crosses another wall',()=>{
    const d=addConnectedWall(draft([w('wall-0001',p(100,200),p(400,200))]),{start:p(250,100),end:p(250,300),estimated_thickness_pixels:10})
    expect(d.walls).toHaveLength(4)
    expect(d.walls.every(w=>[w.start,w.end].some(p=>p.x===250&&p.y===200))).toBe(true)
  })
  it('blocks movement collapse/overlaps and preserves physical opening width during length edits',()=>{
    const d=draft([w('wall-0001',p(0,100),p(400,100)),w('wall-0002',p(400,100),p(400,200))])
    expect(()=>moveConnectedWall(d,{...d.walls[0],end:p(400,200)})).toThrow(/collapse/)
    const withOpening={...draft([d.walls[0]]),openings:[{id:'opening-0001',points:[p(100,100),p(200,100)],disposition:'accepted'}]}
    const resized=moveConnectedWall(withOpening,resizeWall(d.walls[0],600))
    expect(resized.openings[0].points[1].x-resized.openings[0].points[0].x).toBe(100)
  })
})
