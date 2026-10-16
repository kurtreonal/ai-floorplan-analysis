import { readFileSync } from 'node:fs'
import { expect, it } from 'vitest'
import { normalizeCanonicalExtension } from './canonicalExtension.js'
import { normalizeCanonicalGeometry } from './canonicalGeometry.js'
import { buildCanonicalScene } from '../features/viewer-3d/canonicalScene.js'

function fixture() {
  const raw=JSON.parse(readFileSync(new URL('../../../fixtures/canonical_geometry_v1.json',import.meta.url),'utf8'))
  const ext=JSON.parse(readFileSync(new URL('../../../fixtures/canonical_extension_v2_empty.json',import.meta.url),'utf8'))
  const anchor={x:2,y:2,elevation_meters:3}
  raw.routes=[{id:1,points:[{project_floor_id:2,x:1,y:2,elevation_meters:3},{project_floor_id:2,...anchor}]},
    {id:2,points:[{project_floor_id:2,...anchor},{project_floor_id:2,x:2,y:3,elevation_meters:3}]}]
  ext.extension_schema_version=5
  ext.route_details=[[1,1],[2,0]].map(([route_id,point_index])=>({route_id,route_kind:'observed',provenance_ref:'reviewed:test',
    circuit_id:'C1',device_connections:[],junction_connections:[{junction_id:'junction-0001',point_index,anchor:{...anchor}}]}))
  return {raw,ext}
}

it('round trips v5 and pins both 3D branches to the same canonical anchor without another route',()=>{
  const {raw,ext}=fixture(),before=structuredClone(raw)
  expect(normalizeCanonicalExtension(ext,normalizeCanonicalGeometry(raw))).toEqual(ext)
  const scene=buildCanonicalScene(raw,ext)
  expect(scene.routeSegments).toHaveLength(2)
  expect(scene.routeSegments.every(s=>s.connectionAnchors.some(a=>JSON.stringify(a)==='[2,3,2]'))).toBe(true)
  expect(raw).toEqual(before)
})

it.each(['orphan','position','height','index','circuit'])('rejects invalid %s junctions rather than dropping their connectivity',caseName=>{
  const {raw,ext}=fixture(),row=ext.route_details[1],contact=row.junction_connections[0]
  if(caseName==='orphan')row.junction_connections=[]
  if(caseName==='position')contact.anchor.x+=.01
  if(caseName==='height')contact.anchor.elevation_meters+=.01
  if(caseName==='index')contact.point_index=99
  if(caseName==='circuit')row.circuit_id='C2'
  expect(()=>normalizeCanonicalExtension(ext,normalizeCanonicalGeometry(raw))).toThrow()
})
