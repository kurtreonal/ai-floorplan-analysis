import {expect,it} from 'vitest'
import baseFixture from '../../../fixtures/canonical_geometry_v1.json'
import extensionFixture from '../../../fixtures/canonical_extension_v2.json'
import {normalizeCanonicalGeometry} from './canonicalGeometry.js'
import {normalizeCanonicalExtension} from './canonicalExtension.js'

function fixture() {
  const base=normalizeCanonicalGeometry(structuredClone(baseFixture))
  const extension=structuredClone(extensionFixture)
  extension.extension_schema_version=4
  extension.symbol_details[0].installation={elevation_meters:0,wall_id:null}
  const point=base.routes[0].points.at(-1)
  for (const detail of extension.route_details) detail.device_connections=[{
    symbol_id:base.symbols[0].id,point_index:1,
    anchor:{x:point.x,y:point.y,elevation_meters:point.elevation_meters},
  }]
  return {base,extension}
}

it('round trips v4 anchors while preserving old snapshots',()=>{
  const {base,extension}=fixture()
  expect(normalizeCanonicalExtension(extension,base)).toEqual(extension)
  expect(normalizeCanonicalExtension(extensionFixture,base)).toEqual(extensionFixture)
})

it.each(['symbol','index','coordinate','height','duplicate'])('rejects invalid %s attachment',caseName=>{
  const {base,extension}=fixture(), contact=extension.route_details[0].device_connections[0]
  if (caseName==='symbol') contact.symbol_id='detected:999999'
  else if (caseName==='index') contact.point_index=999
  else if (caseName==='coordinate') contact.anchor.x+=.1
  else if (caseName==='height') contact.anchor.elevation_meters+=.1
  else extension.route_details[0].device_connections.push(structuredClone(contact))
  expect(()=>normalizeCanonicalExtension(extension,base)).toThrow()
})
