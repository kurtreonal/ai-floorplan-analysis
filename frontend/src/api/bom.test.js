import {afterEach,expect,it,vi} from 'vitest'
import {fetchBOM,downloadDraftBOM} from './bom.js'
afterEach(()=>vi.unstubAllGlobals())
it('scopes BOM and CSV to the same source plan/job with credentials',async()=>{
  const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({project_id:1,layouts:[],components:[],missing_layout_floors:[],route_state:'unavailable'}),blob:async()=>new Blob(['draft'])})
  vi.stubGlobal('fetch',fetch)
  await fetchBOM(1,{floorPlanId:3,processingJobId:4})
  expect(fetch.mock.calls[0][0]).toMatch(/\/bom\?floor_plan_id=3&processing_job_id=4$/)
  expect(fetch.mock.calls[0][1].credentials).toBe('include')
  await downloadDraftBOM(1,{floorPlanId:3,processingJobId:4})
  expect(fetch.mock.calls[1][0]).toMatch(/\/bom.csv\?floor_plan_id=3&processing_job_id=4$/)
  await expect(fetchBOM(1,{processingJobId:4})).rejects.toThrow()
  await expect(downloadDraftBOM(1,{floorPlanId:-1})).rejects.toThrow()
  expect(fetch).toHaveBeenCalledTimes(2)
})

it('keeps wire, conduit and custom dimensions identical in JSON and CSV requests',async()=>{
  const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({project_id:1,layouts:[],components:[],missing_layout_floors:[],route_state:'unavailable'}),blob:async()=>new Blob(['draft'])})
  vi.stubGlobal('fetch',fetch)
  const options={floorPlanId:3,paperSize:'CUSTOM',customWidthMm:300,customHeightMm:600,conduitMaterialId:9,wireMaterialId:10}
  await fetchBOM(1,options); await downloadDraftBOM(1,options)
  expect(fetch.mock.calls[0][0].split('?')[1]).toBe(fetch.mock.calls[1][0].split('?')[1])
  expect(fetch.mock.calls[0][0]).toContain('wire_material_id=10&custom_width_mm=300&custom_height_mm=600')
  await expect(fetchBOM(1,{...options,customWidthMm:0})).rejects.toThrow()
  await expect(fetchBOM(1,{...options,customHeightMm:NaN})).rejects.toThrow()
})

it('passes wire conversion and manual per-metre price to both exports including zero',async()=>{
  const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({project_id:1,layouts:[],components:[],missing_layout_floors:[],route_state:'unavailable'}),blob:async()=>new Blob(['draft'])})
  vi.stubGlobal('fetch',fetch)
  const options={floorPlanId:3,wireMaterialId:10,wireMetersPerUnit:100,wirePricePerMeter:0}
  await fetchBOM(1,options); await downloadDraftBOM(1,options)
  expect(fetch.mock.calls[0][0]).toContain('wire_meters_per_unit=100&wire_price_per_meter=0')
  expect(fetch.mock.calls[0][0].split('?')[1]).toBe(fetch.mock.calls[1][0].split('?')[1])
  await expect(fetchBOM(1,{wireMetersPerUnit:100})).rejects.toThrow()
  await expect(fetchBOM(1,{wirePricePerMeter:-1})).rejects.toThrow()
})

it('exports the same draft material and paper assumption, refusing invalid scope',async()=>{
  const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({project_id:1,layouts:[],components:[],missing_layout_floors:[],route_state:'unavailable'}),blob:async()=>new Blob(['draft'])})
  vi.stubGlobal('fetch',fetch)
  const options={floorPlanId:3,processingJobId:4,conduitMaterialId:9,paperSize:'A3'}
  await fetchBOM(1,options); await downloadDraftBOM(1,options)
  expect(fetch.mock.calls[0][0]).toContain('conduit_material_id=9&paper_size=A3')
  expect(fetch.mock.calls[1][0]).toContain('conduit_material_id=9&paper_size=A3')
  await expect(fetchBOM(1,{paperSize:'A3'})).rejects.toThrow()
  await expect(fetchBOM(1,{floorPlanId:3,paperSize:'CUSTOM'})).rejects.toThrow()
  await expect(fetchBOM(1,{conduitMaterialId:-1})).rejects.toThrow()
  expect(fetch).toHaveBeenCalledTimes(2)
})
