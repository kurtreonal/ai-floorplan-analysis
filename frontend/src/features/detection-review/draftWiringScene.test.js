import { describe, expect, it } from 'vitest'
import { buildDraftRoomScene } from './draftRoomScene.js'
import { moveDraftWirePoint } from './draftWiringScene.js'

const wire = { id: 'w1', points: [{ x: 300, y: 50 }, { x: 600, y: 250 }, { x: 700, y: 300 }], disposition: 'unresolved', completeness: 'partial', elevation_meters: null }
const draft = { walls: [], rooms: [], symbols: [], wirings: [wire] }
describe('whole-plan advisory wiring projection', () => {
  it('counts a ceiling terminal already on the source route without inventing a zero-length connector', () => {
    const source={...draft,symbols:[{id:'s',center:{x:300,y:50}}],wirings:[{...wire,
      device_attachments:[{symbol_id:'s',point_index:0}]}]}
    const scene=buildDraftRoomScene(source,800,400,.75,{s:{family:'troffer'}})
    expect(scene.draftWires[0].deviceIds).toEqual(['s'])
    expect(scene.draftWires[0].segments).toHaveLength(2)
  })
  it('connects shared attached wires to the rear terminal once, including an illustrative drop when dimensions are missing', () => {
    const source={walls:[{id:'wall',start:{x:0,y:50},end:{x:800,y:50}}],rooms:[],
      symbols:[{id:'s',center:{x:300,y:50},mounting_height_meters:1.2,mounting_wall_id:'wall'}],
      wirings:[{...wire,points:[{x:100,y:50},{x:300,y:50}],elevation_meters:8.8,device_attachments:[{symbol_id:'s',point_index:1}]},
        {...wire,id:'w2',points:[{x:300,y:50},{x:600,y:50}],elevation_meters:8.8,device_attachments:[{symbol_id:'s',point_index:0}]}]}
    const before=structuredClone(source)
    const scene=buildDraftRoomScene(source,800,400,.75,{s:{family:'switch'}},{floorElevationMeters:6})
    const drops=scene.draftWires.flatMap(w => w.segments).filter(s => s.previewDrop)
    expect(drops).toHaveLength(1)
    expect(drops[0].illustrative).toBe(false)
    expect(drops[0].start[1]-drops[0].end[1]).toBeCloseTo(1.6*scene.unitsPerMeter)
    expect(scene.symbols[0].installation.elevation_meters).toBe(1.2)
    const preview=buildDraftRoomScene(source,800,400,.75,{s:{family:'switch'}})
    expect(preview.draftWires.flatMap(w => w.segments).filter(s => s.previewDrop)).toHaveLength(1)
    expect(preview.draftWires[0].segments.find(s => s.previewDrop).illustrative).toBe(true)
    expect(source).toEqual(before)
  })
  it('retains the installation and line design of every wiring origin in 3D without changing source points', () => {
    const source = { ...draft, wirings: [
      { ...wire, installation_method: 'concealed_in_ceiling', line_style: 'solid' },
      { ...wire, id: 'generated', origin: 'generated', installation_method: 'concealed_under_floor', line_style: 'dashed' },
    ] }
    const before = structuredClone(source)
    const scene = buildDraftRoomScene(source, 800, 400, .75)
    expect(scene.draftWires[0]).toMatchObject({ installationMethod: 'concealed_in_ceiling', lineStyle: 'solid' })
    expect(scene.draftWires[1]).toMatchObject({ installationMethod: 'concealed_under_floor', lineStyle: 'dashed', origin: 'generated' })
    expect(source).toEqual(before)
  })
  it('does not connect shared touching traces to a nearby device without explicit attachments', () => {
    const source = { walls: [{ id: 'wall', start: { x: 0, y: 50 }, end: { x: 800, y: 50 } }], rooms: [],
      symbols: [{ id: 'socket', center: { x: 300, y: 50 } }], wirings: [
        { ...wire, points: [{ x: 100, y: 50 }, { x: 300, y: 50 }] },
        { ...wire, id: 'w2', points: [{ x: 300, y: 50 }, { x: 500, y: 50 }] },
      ] }
    const before = structuredClone(source)
    const scene = buildDraftRoomScene(source,800,400,.75,{ socket: { family: 'outlet' } })
    const segments = scene.draftWires.flatMap(w => w.segments)
    expect(segments.filter(s => s.previewDrop || s.deviceId)).toHaveLength(0)
    expect(source).toEqual(before)
  })
  it('keeps generated branch joins in literal contact in the shared 3D projection', () => {
    const source = { ...draft, wirings: [
      { ...wire, id:'branch-a', origin:'generated', points:[{x:40,y:40},{x:70,y:40}] },
      { ...wire, id:'branch-b', origin:'generated', points:[{x:240,y:140},{x:270,y:140}] },
      { ...wire, id:'join', origin:'generated', points:[{x:70,y:40},{x:240,y:40},{x:240,y:140}] },
    ] }
    const before=structuredClone(source)
    const scene=buildDraftRoomScene(source,800,400,.75)
    const [a,b,join]=scene.draftWires
    expect(join.points[0]).toEqual(a.points.at(-1))
    expect(join.points.at(-1)).toEqual(b.points[0])
    expect(join.segments.every(s => s.start[1] === .75 && s.end[1] === .75)).toBe(true)
    expect(join.origin).toBe('generated')
    expect(source).toEqual(before)
  })
  it('uses source geometry for arbitrary pages, without approval or an invented box', () => {
    const before = structuredClone(draft)
    const scene = buildDraftRoomScene(draft,800,400,.75)
    expect(scene.draftWires[0]).toMatchObject({ id: 'w1', illustrativeHeight: true,
      points: [[3.75,.75,.625],[7.5,.75,3.125],[8.75,.75,3.75]] })
    expect(scene.draftWires[0].segments).toHaveLength(2)
    expect(scene.previewOnly).toBe(true)
    expect(draft).toEqual(before)
    expect(wire.elevation_meters).toBeNull()
  })
  it('preserves explicit heights including underground and excludes rejected/invalid traces', () => {
    const scene = buildDraftRoomScene({ ...draft, wirings: [{ ...wire, elevation_meters: -.4 },
      { ...wire, id: 'deleted', disposition: 'rejected' }, { ...wire, id: 'invalid', points: [{ x: -1, y: 0 }, { x: 50, y: 50 }] }] },800,400)
    expect(scene.draftWires).toHaveLength(1)
    expect(scene.invalidWiringCount).toBe(1)
    expect(scene.draftWires[0].illustrativeHeight).toBe(true) // Absolute elevation without a floor datum remains illustrative.
    expect(scene.draftWires[0].points.every(p => p[1] === -.1)).toBe(true)
  })
  it('projects catalog under-floor routes at the floor reference, never an invented depth or ceiling', () => {
    const source={...draft,wirings:[{...wire,installation_method:'concealed_under_floor'}]}
    const before=structuredClone(source)
    const scene=buildDraftRoomScene(source,800,400,.75)
    expect(scene.draftWires[0].points.every(p=>p[1]===0)).toBe(true)
    expect(scene.draftWires[0].installationMethod).toBe('concealed_under_floor')
    expect(scene.draftWires[0].illustrativeHeight).toBe(true)
    expect(source).toEqual(before)
  })
  it('does not invent a measured drop at a touching wall-device endpoint', () => {
    const source = { walls: [{ id: 'wall', start: { x: 0, y: 50 }, end: { x: 800, y: 50 } }], rooms: [],
      symbols: [{ id: 's', center: { x: 300, y: 50 } }], wirings: [wire] }
    const before = structuredClone(source)
    const scene = buildDraftRoomScene(source,800,400,.75,{ s: { family: 'switch' } })
    const drops = scene.draftWires[0].segments.filter(s => s.previewDrop)
    expect(drops).toHaveLength(0)
    expect(source).toEqual(before)
    const ambiguous = buildDraftRoomScene({ ...source, symbols: [...source.symbols, { id: 's2', center: { x: 300, y: 50 } }] },800,400,.75,{ s: { family: 'switch' }, s2: { family: 'switch' } })
    expect(ambiguous.draftWires[0].segments.some(s => s.previewDrop)).toBe(false)
    expect(buildDraftRoomScene(source,800,400,.75,{ s: { family: 'unknown' } }).draftWires[0].segments.some(s => s.previewDrop)).toBe(false)
  })
  it('edits one source point immutably, clamps to the page and preserves unknown height', () => {
    const before = structuredClone(wire)
    expect(moveDraftWirePoint(wire,1,{ x: 900, y: -10 },800,400)).toEqual({ ...wire,
      points: [wire.points[0],{ x: 800, y: 0 },wire.points[2]], disposition: 'corrected' })
    expect(moveDraftWirePoint(wire,1,wire.points[0],800,400)).toBeNull()
    expect(moveDraftWirePoint(wire,-1,{ x: 50, y: 50 },800,400)).toBeNull()
    expect(moveDraftWirePoint({...wire,origin:'generated',suppression_reason:'redundant_observed_connection'},
      1,{x:650,y:250},800,400).suppression_reason).toBeNull()
    expect(wire).toEqual(before)
  })
  it('keeps masked light edges and intermediate wall devices unresolved without a junction', () => {
    const source = { walls: [{ id: 'wall', start: { x: 0, y: 150 }, end: { x: 800, y: 150 } }], rooms: [],
      symbols: [{ id: 'light', center: { x: 100, y: 50 } }, { id: 's', center: { x: 400, y: 150 } }],
      wirings: [{ ...wire, points: [{ x: 123, y: 50 }, { x: 400, y: 150 }, { x: 700, y: 300 }] }] }
    const before = structuredClone(source)
    const scene = buildDraftRoomScene(source,800,400,.75,{
      light: { family: 'linear-light', sourceBounds: { x: 85,y: 35,width: 30,height: 30 } }, s: { family: 'switch' },
    })
    const segments = scene.draftWires[0].segments
    expect(segments.some(s => s.deviceId || s.previewDrop)).toBe(false)
    expect(segments.every(s => Math.hypot(...s.end.map((v,i) => v-s.start[i]))>0)).toBe(true)
    expect(source).toEqual(before)
  })
  it('does not fabricate distant attachments or overwrite explicit underground heights', () => {
    const source = { ...draft, symbols: [{ id: 's', center: { x: 20, y: 20 } }] }
    const scene = buildDraftRoomScene(source,800,400,.75,{ s: { family: 'switch' } })
    expect(scene.draftWires[0].segments.every(s => !s.deviceId)).toBe(true)
    const underground = buildDraftRoomScene({ ...source, symbols: [{id: 's',center: wire.points[0]}],
      wirings: [{ ...wire,elevation_meters: -.4 }] },800,400,.75,{s:{family:'switch'}})
    expect(underground.draftWires[0].segments.every(s => !s.deviceId && s.end[1] === -.1)).toBe(true)
    const unmounted = buildDraftRoomScene({ ...source,symbols:[{id:'s',center:wire.points[0]}] },800,400,.75,{s:{family:'switch'}})
    expect(unmounted.draftWires[0].segments.every(s => !s.deviceId)).toBe(true)
  })
})
