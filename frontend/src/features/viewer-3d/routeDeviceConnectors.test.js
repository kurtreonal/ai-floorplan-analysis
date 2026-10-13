import { expect, it } from 'vitest'
import { routeDeviceConnectors } from './routeDeviceConnectors.js'
import { devicePlacement, deviceConnector } from './devicePlacement.js'

const symbol = { id: 's',classification: { name: 'Wall switch' },position: [2,0,1],
  installation: { provenance: 'designer_supplied_planning',elevation_meters: 1.2,wall_id: 'w' } }
const scene = { elevation: 0,width: 10,depth: 10,walls: [{ id: 'w',position: [5,1.5,1],size: [10,3,.18],rotation: [0,0,0] }],symbols: [symbol] }
const segments = [{ kind: 'wall_drop',start: { x: 2,y: 1,elevation_meters: 3 },end: { x: 2,y: 1,elevation_meters: 1.2 } }]

it('terminates the displayed route at the rendered switch without changing measured geometry', () => {
  const before = structuredClone({scene,segments})
  const leads = routeDeviceConnectors(scene,segments)
  const placement = devicePlacement(symbol,scene,'switch')
  expect(leads).toHaveLength(1)
  const rear=deviceConnector(placement)
  expect(leads[0].end).toEqual({x:rear[0],y:rear[2],elevation_meters:rear[1]})
  expect(leads[0].end.y).toBeLessThan(placement.position[2])
  expect(leads[0].provenance).toBe('display_attachment_not_measurement')
  expect({scene,segments}).toEqual(before)
})

it('does not connect nearby unrelated wires, uncertain installations or drafts', () => {
  expect(routeDeviceConnectors(scene,[{...segments[0],end:{...segments[0].end,x:2.01}}])).toEqual([])
  expect(routeDeviceConnectors({...scene,previewOnly:true},segments)).toEqual([])
  expect(routeDeviceConnectors({...scene,symbols:[{...symbol,installation:null}]},segments)).toEqual([])
  expect(routeDeviceConnectors({...scene,symbols:[{...symbol,installation:{...symbol.installation,floor_id:2}}]},
    segments.map(s => ({...s,start:{...s.start,floor_id:3},end:{...s.end,floor_id:3}})))).toEqual([])
})
