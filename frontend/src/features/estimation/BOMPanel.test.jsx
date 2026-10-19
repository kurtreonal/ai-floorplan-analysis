/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { fetchBOM, downloadBOM, downloadDraftBOM } from '../../api/bom.js'
import { BOMPanel } from './BOMPanel.jsx'
vi.mock('../../api/bom.js', () => ({ fetchBOM: vi.fn(), downloadBOM: vi.fn(), downloadDraftBOM:vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.unstubAllGlobals() })
it('alphabetizes material choices and table rows without changing the source prices or identities',async()=>{
  const planning={items:[{kind:'device',class_id:2,name:'Switch',quantity:2,unit:'piece',unit_price:'7',currency:'PHP',line_total:'14'},
    {kind:'device',class_id:1,name:'Lamp',quantity:3,unit:'piece',unit_price:'5',currency:'PHP',line_total:'15'}],
    priced_subtotals:{PHP:'29'},unpriced_items:0,basis:[],catalog_materials:2,
    conduit_materials:[{id:10,name:'Tube 10',unit:'meter',unit_price:10,currency:'PHP'},{id:2,name:'Tube 2',unit:'meter',unit_price:2,currency:'PHP'}],
    wire_materials:[{id:11,name:'Z wire',unit:'meter',unit_price:11,currency:'PHP'},{id:1,name:'A wire',unit:'meter',unit_price:1,currency:'PHP'}]}
  const before=JSON.stringify(planning)
  fetchBOM.mockResolvedValue({planning})
  render(<BOMPanel projectId={1} floorPlanId={3} />)
  const conduit=await screen.findByLabelText('Conduit product for this draft')
  expect(Array.from(conduit.options).map(item=>item.value)).toEqual(['','2','10'])
  expect(Array.from(screen.getByLabelText('Wire / cable product for this draft').options).map(item=>item.value)).toEqual(['','1','11'])
  expect(Array.from(screen.getByRole('table',{name:'Draft bill of materials'}).querySelectorAll('tbody tr')).map(row=>row.cells[0].textContent)).toEqual(['LampDevice count','SwitchDevice count'])
  expect(JSON.stringify(planning)).toBe(before)
})
it('shows reviewed quantities without needing a route and downloads only a saved snapshot', async () => {
  fetchBOM.mockResolvedValue({ layouts: [{ floor_id: 2 }], components: [{ floor_id: 2, class_id: 1, name: 'Switch', quantity: 3 }], route_lengths: null, missing_layout_floors: [3] })
  downloadBOM.mockResolvedValue(new Blob(['saved prices']))
  URL.createObjectURL = vi.fn(() => 'blob:test'); URL.revokeObjectURL = vi.fn()
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  const view = render(<BOMPanel projectId={1} estimate={null} />)
  await screen.findByText('Switch')
  expect(screen.getByText('Download saved BOM').disabled).toBe(true)
  expect(screen.getByText(/await a current measured route/)).toBeTruthy()
  view.rerender(<BOMPanel projectId={1} estimate={{ id: 8, version_number: 2 }} />)
  fireEvent.click(screen.getByText('Download saved BOM'))
  await waitFor(() => expect(click).toHaveBeenCalled())
  expect(downloadBOM).toHaveBeenCalledWith(1, 8, expect.objectContaining({ signal: expect.any(AbortSignal) }))
  click.mockRestore()
})
it('shows approved drawing wiring types separately without fabricating quantity or price', async () => {
  fetchBOM.mockResolvedValue({layouts:[],components:[],route_lengths:null,missing_layout_floors:[2],
    wiring_types:[{floor_plan_id:8,wiring_legend_id:1790,name:'Raceway conduit concealed under floor [pdf-test:p1:L10]',quantity_meters:null}]})
  render(<BOMPanel projectId={1} estimate={null} />)
  await screen.findByText(/Raceway conduit concealed under floor/)
  expect(screen.getByText(/Draft types only/)).toBeTruthy()
  expect(screen.getByText('Download saved BOM').disabled).toBe(true)
})

it('automatically shows priced draft devices and missing scale without approval controls', async () => {
  fetchBOM.mockResolvedValue({planning:{items:[{kind:'device',class_id:1,name:'Lamp',quantity:2,unit:'piece',unit_price:'10',currency:'PHP',line_total:'20',pricing_state:'priced'},
    {kind:'path',path_id:'segment-0001',name:'Ceiling conduit',quantity:200,unit:'source pixel',line_total:null,pricing_state:'scale_required'}],
    priced_subtotals:{PHP:'20'},unpriced_items:1,basis:['Count active devices.'],catalog_materials:12}})
  downloadDraftBOM.mockResolvedValue(new Blob(['DRAFT BOM']))
  URL.createObjectURL=vi.fn(()=> 'blob:draft'); URL.revokeObjectURL=vi.fn()
  const click=vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{})
  const view=render(<BOMPanel projectId={1} floorPlanId={3} processingJobId={4} />)
  await screen.findByText('Lamp')
  const table = screen.getByRole('table',{name:'Draft bill of materials'})
  expect(table.closest('[aria-label="Draft material costs"]').tabIndex).toBe(0)
  expect(within(table).getAllByRole('columnheader')).toHaveLength(4)
  expect(table.querySelector('tfoot').textContent).toContain('Priced subtotal (PHP)')
  expect(table.querySelector('tfoot').textContent).toContain('₱20.00')
  expect(screen.getByText('Set plan scale once')).toBeTruthy()
  expect(screen.queryByRole('checkbox')).toBeNull()
  expect(screen.getByText(/Subtotals are incomplete/)).toBeTruthy()
  fireEvent.click(screen.getByText('Download draft BOM'))
  await waitFor(()=>expect(click).toHaveBeenCalled())
  expect(downloadDraftBOM).toHaveBeenCalledWith(1,expect.objectContaining({floorPlanId:3,processingJobId:4}))
  view.rerender(<BOMPanel projectId={1} floorPlanId={3} processingJobId={4} refreshKey={2} />)
  await waitFor(()=>expect(fetchBOM).toHaveBeenCalledTimes(2))
  click.mockRestore()
})

it('retains conduit selection and paper metadata without treating paper size as calibration',async()=>{
  const planning={items:[],priced_subtotals:{},unpriced_items:0,basis:[],catalog_materials:1,
    conduit_materials:[{id:9,name:'EMT half-inch',unit:'length',unit_price:'360',currency:'PHP'}]}
  fetchBOM.mockResolvedValue({planning})
  const view=render(<BOMPanel projectId={1} floorPlanId={3} processingJobId={4} />)
  const conduit=await screen.findByLabelText('Conduit product for this draft')
  fireEvent.change(conduit,{target:{value:'9'}})
  await waitFor(()=>expect(fetchBOM).toHaveBeenLastCalledWith(1,expect.objectContaining({conduitMaterialId:9})))
  fireEvent.change(screen.getByLabelText('Paper metadata (not calibration)'),{target:{value:'A3'}})
  await waitFor(()=>expect(fetchBOM).toHaveBeenLastCalledWith(1,expect.objectContaining({conduitMaterialId:9,paperSize:'A3'})))
  expect(screen.getByText(/Paper size alone cannot calibrate/)).toBeTruthy()
  expect(screen.queryByRole('checkbox')).toBeNull()
  view.rerender(<BOMPanel projectId={2} floorPlanId={5} processingJobId={6} />)
  await waitFor(()=>expect(fetchBOM).toHaveBeenLastCalledWith(2,expect.objectContaining({conduitMaterialId:undefined,paperSize:'A3'})))
})

it('uses independent wire selection and custom dimensions only after apply, resetting scope',async()=>{
  fetchBOM.mockResolvedValue({planning:{items:[],priced_subtotals:{},unpriced_items:0,basis:[],
    conduit_materials:[{id:9,name:'EMT',unit:'length',unit_price:10,currency:'PHP'}],
    wire_materials:[{id:10,name:'THHN wire',unit:'meter',unit_price:20,currency:'PHP'}]}})
  render(<BOMPanel projectId={1} floorPlanId={3} processingJobId={4} />)
  fireEvent.change(await screen.findByLabelText('Conduit product for this draft'),{target:{value:'9'}})
  fireEvent.change(screen.getByLabelText('Wire / cable product for this draft'),{target:{value:'10'}})
  fireEvent.change(screen.getByLabelText('Paper metadata (not calibration)'),{target:{value:'CUSTOM'}})
  fireEvent.change(screen.getByLabelText('Sheet width (mm)'),{target:{value:'300'}})
  fireEvent.change(screen.getByLabelText('Sheet height (mm)'),{target:{value:'600'}})
  fireEvent.click(screen.getByText('Apply custom dimensions'))
  await waitFor(()=>expect(fetchBOM).toHaveBeenLastCalledWith(1,expect.objectContaining({conduitMaterialId:9,wireMaterialId:10,paperSize:'CUSTOM',customWidthMm:300,customHeightMm:600})))
})

it('applies roll conversion or custom wire price without an allowance charge or stale product conversion',async()=>{
  fetchBOM.mockResolvedValue({planning:{items:[],priced_subtotals:{},unpriced_items:0,basis:[],
    wire_materials:[{id:10,name:'THHN wire',unit:'roll',unit_price:2000,currency:'PHP'},
      {id:11,name:'Wire by metre',unit:'meter',unit_price:20,currency:'PHP'}]}})
  render(<BOMPanel projectId={1} floorPlanId={3} />)
  fireEvent.change(await screen.findByLabelText('Wire / cable product for this draft'),{target:{value:'10'}})
  fireEvent.change(screen.getByLabelText('Metres per wire purchase unit'),{target:{value:'100'}})
  fireEvent.change(screen.getByLabelText('Custom wire price per metre (PHP, optional)'),{target:{value:'25'}})
  fireEvent.click(screen.getByText('Apply wire pricing'))
  await waitFor(()=>expect(fetchBOM).toHaveBeenLastCalledWith(1,expect.objectContaining({wireMaterialId:10,wireMetersPerUnit:100,wirePricePerMeter:25})))
  fireEvent.change(screen.getByLabelText('Wire / cable product for this draft'),{target:{value:'11'}})
  await waitFor(()=>expect(fetchBOM).toHaveBeenLastCalledWith(1,expect.objectContaining({wireMaterialId:11,wireMetersPerUnit:undefined,wirePricePerMeter:undefined})))
  expect(screen.queryByLabelText('Metres per wire purchase unit')).toBeNull()
  expect(screen.getByText(/No extra allowance is added/)).toBeTruthy()
})
