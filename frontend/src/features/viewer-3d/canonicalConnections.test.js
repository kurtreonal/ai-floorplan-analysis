import {expect,it} from 'vitest'
import fixture from '../../../../fixtures/canonical_geometry_v1.json'
import {buildCanonicalScene} from './canonicalScene.js'
import {devicePlacement,deviceConnector} from './devicePlacement.js'
import {displayWiringRuns} from '../routing/wiringPresentation.js'

function connected() {
  const geometry=structuredClone(fixture)
  geometry.walls.forEach(w => Object.assign(w,{status:'verified',height_meters:3,thickness_meters:.18}))
  const symbol=geometry.symbols[0];symbol.position={x:2.5,y:.35}
  const source={project_floor_id:2,x:2.5,y:.35,elevation_meters:-1.5}
  const mount={...source,elevation_meters:-1.05}
  geometry.routes=[{id:1,points:[{...source,x:1},source,{...source,x:4}]},{id:2,points:[source,mount]}]
  const anchor={x:2.5,y:.35,elevation_meters:-1.05}
  const extension={extension_schema_version:4,base_schema_version:1,
    source_plane_reference:{floor_plan_page_id:1,source_artifact_id:2,width_pixels:640,height_pixels:480},
    openings:[],panels:[],symbol_details:[{symbol_id:symbol.id,orientation_degrees:null,bounds:null,provenance:null,
      installation:{elevation_meters:-1.05,wall_id:geometry.walls[0].id}}],
    route_details:geometry.routes.map(r => ({route_id:r.id,route_kind:'observed',provenance_ref:null,
      device_connections:[{symbol_id:symbol.id,point_index:1,anchor}]}))}
  return {geometry,extension}
}

it('projects one stored under-floor rise to the outlet rear terminal without another route or measurement mutation',()=>{
  const {geometry,extension}=connected(),before=structuredClone({geometry,extension})
  const scene=buildCanonicalScene(geometry,extension)
  const outlet=scene.symbols[0],rear=deviceConnector(devicePlacement(outlet,scene,'outlet'))
  const branch=scene.routeSegments.filter(s => s.routeId===2)
  expect(branch.at(-1).end).toEqual(rear)
  const vertical=branch.filter(s => s.start[1]!==s.end[1])
  expect(vertical).toHaveLength(1)
  expect(vertical[0].end[1]-vertical[0].start[1]).toBeCloseTo(.45)
  expect(vertical[0].start[0]).toBe(vertical[0].end[0])
  expect(vertical[0].start[2]).toBe(vertical[0].end[2])
  expect(new Set(scene.routeSegments.map(s => s.routeId)).size).toBe(2)
  expect({geometry,extension}).toEqual(before)
})

it('rejects stale device anchors and preserves legacy versions',()=>{
  const {geometry,extension}=connected()
  extension.route_details[0].device_connections[0].anchor.x=2.6
  expect(()=>buildCanonicalScene(geometry,extension)).toThrow()
  extension.extension_schema_version=3
  expect(()=>buildCanonicalScene(geometry,extension)).toThrow() // v4 fields cannot leak into old snapshots.
})

it('pins an inline terminal during display-only overlap spacing',()=>{
  const anchor=[1,2,0]
  const runs=displayWiringRuns([{id:'a',ownerId:'a',points:[[0,2,0],anchor,[2,2,0]],connectionAnchors:[anchor]},
    {id:'b',ownerId:'b',points:[[0,2,0],[2,2,0]]}],.01)
  expect(runs[0].points).toContainEqual(anchor)
  expect(runs[0].laneOffset).not.toBe(0)
})
