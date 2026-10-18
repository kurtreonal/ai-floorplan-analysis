import {expect,it} from 'vitest'
import baseFixture from '../../../fixtures/canonical_geometry_v1.json'
import extensionFixture from '../../../fixtures/canonical_extension_v2.json'
import {normalizeCanonicalGeometry} from './canonicalGeometry.js'
import {normalizeCanonicalExtension} from './canonicalExtension.js'

it('round trips additive v6 terminal, vertex and lineage references; v2 is untouched and v5 fails closed',()=>{
  const base=normalizeCanonicalGeometry(structuredClone(baseFixture)), ext=structuredClone(extensionFixture)
  ext.extension_schema_version=6
  ext.symbol_details[0].installation={elevation_meters:0,wall_id:null}
  const p=base.routes[0].points.at(-1)
  for(const d of ext.route_details)Object.assign(d,{circuit_id:null,junction_connections:[],vertex_ids:['a','b'],network_lineage:['segment-0001'],device_connections:[{
    symbol_id:base.symbols[0].id,point_index:1,terminal_id:'design-anchor',anchor:{x:p.x,y:p.y,elevation_meters:p.elevation_meters},
  }]})
  expect(normalizeCanonicalExtension(ext,base)).toEqual(ext)
  expect(normalizeCanonicalExtension(extensionFixture,base)).toEqual(extensionFixture)
  expect(()=>normalizeCanonicalExtension({...ext,extension_schema_version:5},base)).toThrow()
  const extraId=Math.max(...base.routes.map(r=>r.id))+1
  const expanded=normalizeCanonicalGeometry({...base,routes:[...base.routes,{...base.routes[0],id:extraId}]})
  const conflict=structuredClone(ext)
  conflict.route_details.push({...structuredClone(ext.route_details[0]),route_id:extraId,circuit_id:'different'})
  expect(()=>normalizeCanonicalExtension(conflict,expanded)).toThrow()
  ext.route_details[0].vertex_ids=['one']
  expect(()=>normalizeCanonicalExtension(ext,base)).toThrow()
})
