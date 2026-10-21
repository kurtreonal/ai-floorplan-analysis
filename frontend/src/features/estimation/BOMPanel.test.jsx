/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { fetchBOM, downloadBOM, downloadDraftBOM } from '../../api/bom.js'
import { BOMPanel } from './BOMPanel.jsx'
import { uploadAutomaticPrices } from '../../api/projectPricing.js'
vi.mock('../../api/bom.js', () => ({ fetchBOM: vi.fn(), downloadBOM: vi.fn(), downloadDraftBOM:vi.fn() }))
vi.mock('../../api/projectPricing.js',()=>({uploadAutomaticPrices:vi.fn(),listProjectPrices:vi.fn().mockResolvedValue([])}))
vi.mock('../../api/itemPricing.js',()=>({fetchItemPrices:vi.fn(),previewItemPrices:vi.fn(),applyItemPrices:vi.fn()}))
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.unstubAllGlobals() })
it('keeps measurement details out of the BOM and shows one small warning',async()=>{
  const planning={items:[{kind:'path',name:'Wire/cable',quantity:10,unit:'meter',pricing_state:'measurement_incomplete',missing_vertical_inputs:['device-1: save device mounting height for the connected drop/rise']}],priced_subtotals:{},unpriced_items:1,basis:['Technical basis'],missing_inputs:['Technical scale note'],conduit_materials:[]}
  fetchBOM.mockResolvedValue({planning})
  const before=JSON.stringify(planning)
  render(<BOMPanel projectId={1} floorPlanId={3}/>)
  expect(await screen.findByText('Some items need prices or measurements. Any subtotal is partial.')).toBeTruthy()
  expect(screen.queryByText('Connected · drop/rise inputs needed')).toBeNull()
  expect(screen.queryByText('Calculation basis')).toBeNull()
  expect(screen.queryByText('Optional material and measurement overrides')).toBeNull()
  expect(screen.queryByText('Technical scale note')).toBeNull()
  expect(screen.queryByText('device-1: save device mounting height for the connected drop/rise')).toBeNull()
  expect(screen.getByRole('table').querySelector('tfoot').textContent).toBe('Total—')
  expect(JSON.stringify(planning)).toBe(before)
})

it('explicitly separates saved BOM quantities when the canvas has unsaved edits',async()=>{
  fetchBOM.mockResolvedValue({planning:{items:[],priced_subtotals:{},unpriced_items:0,basis:[],conduit_materials:[]}})
  render(<BOMPanel projectId={1} floorPlanId={3} unsaved />)
  expect(screen.getByText('Unsaved changes: this BOM shows saved items. Save to refresh quantities.')).toBeTruthy()
  expect(await screen.findByText('No saved devices or wiring yet.')).toBeTruthy()
})
it('automatically applies uploaded client prices without review or selection and refreshes the same compact table', async () => {
  const item={item_key:'a'.repeat(64),kind:'device',item_kind:'device',class_id:1,name:'Outlet',quantity:1,unit:'piece',material_id:3,unit_price:'100',currency:'PHP',line_total:'100',pricing_state:'priced',compatible_prices:['Quote:2']}
  fetchBOM.mockResolvedValue({planning:{sources:[{floor_id:2}],items:[item],priced_subtotals:{PHP:'100'},unpriced_items:0,basis:[],
    conduit_materials:[{id:9,name:'Conduit',unit:'meter',unit_price:10,currency:'PHP'}]}})
  uploadAutomaticPrices.mockResolvedValue({price_version_id:7,applied:1,skipped:[],skipped_rows:[]})
  const draft = {candidate_run_id:'test',symbols:[{id:'symbol-0001',center:{x:20,y:30}}]}
  const before = JSON.stringify(draft)
  render(<BOMPanel projectId={1} floorPlanId={3} processingJobId={4} designer draftPreview={draft} />)
  await screen.findByRole('table')
  const file=new File(['test'],'synthetic.xlsx')
  const previous = fetchBOM.mock.calls.length
  fireEvent.change(screen.getByLabelText('Upload client BOM file'),{target:{files:[file]}})
  await screen.findByText('Client prices applied to 1 device/wiring components.')
  expect(await screen.findAllByRole('table')).toHaveLength(1)
  await waitFor(() => expect(fetchBOM.mock.calls.length).toBe(previous+1))
  expect(fetchBOM).toHaveBeenLastCalledWith(1,expect.objectContaining({floorPlanId:3,processingJobId:4}))
  expect(JSON.stringify(draft)).toBe(before)
  expect(uploadAutomaticPrices).toHaveBeenCalledWith(1,file,expect.objectContaining({floorId:2,requestId:expect.any(String)}))
  expect(screen.queryByText('Use imported prices')).toBeNull()
  expect(screen.queryByText('Check mappings')).toBeNull()
  expect(screen.queryByRole('checkbox')).toBeNull()
})

it('exposes one upload in workspace and cost estimation only for Designers', () => {
  fetchBOM.mockReturnValue(new Promise(() => {}))
  const view = render(<BOMPanel projectId={1} floorPlanId={3} designer={false} />)
  expect(screen.queryByRole('button',{name:'Upload BOM',exact:true})).toBeNull()
  view.rerender(<BOMPanel projectId={1} designer />)
  expect(screen.getAllByRole('button',{name:'Upload BOM',exact:true})).toHaveLength(1)
})

it('alphabetizes compact rows without changing the source prices or identities',async()=>{
  const planning={items:[{kind:'device',class_id:2,name:'Switch',quantity:2,unit:'piece',unit_price:'7',currency:'PHP',line_total:'14'},
    {kind:'device',class_id:1,name:'Lamp',quantity:3,unit:'piece',unit_price:'5',currency:'PHP',line_total:'15'}],
    priced_subtotals:{PHP:'29'},unpriced_items:0,basis:[],catalog_materials:2,
    conduit_materials:[{id:10,name:'Tube 10',unit:'meter',unit_price:10,currency:'PHP'},{id:2,name:'Tube 2',unit:'meter',unit_price:2,currency:'PHP'}],
    wire_materials:[{id:11,name:'Z wire',unit:'meter',unit_price:11,currency:'PHP'},{id:1,name:'A wire',unit:'meter',unit_price:1,currency:'PHP'}]}
  const before=JSON.stringify(planning)
  fetchBOM.mockResolvedValue({planning})
  render(<BOMPanel projectId={1} floorPlanId={3} />)
  await screen.findByRole('table')
  expect(Array.from(screen.getByRole('table',{name:'Draft bill of materials'}).querySelectorAll('tbody tr')).map(row=>row.cells[0].textContent)).toEqual(['Lamp','Switch'])
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
  expect(screen.getByText('Unmeasured')).toBeTruthy()
  expect(screen.queryByRole('checkbox')).toBeNull()
  expect(screen.getByText(/Any subtotal is partial/)).toBeTruthy()
  fireEvent.click(screen.getByText('Download draft BOM'))
  await waitFor(()=>expect(click).toHaveBeenCalled())
  expect(downloadDraftBOM).toHaveBeenCalledWith(1,expect.objectContaining({floorPlanId:3,processingJobId:4}))
  view.rerender(<BOMPanel projectId={1} floorPlanId={3} processingJobId={4} refreshKey={2} />)
  await waitFor(()=>expect(fetchBOM).toHaveBeenCalledTimes(2))
  click.mockRestore()
})

it('keeps scope and authorization while removing calculator controls',async()=>{
  fetchBOM.mockResolvedValue({planning:{items:[],priced_subtotals:{},unpriced_items:0,basis:[],sources:[{floor_id:2}]}})
  const view=render(<BOMPanel projectId={1} floorPlanId={3} designer />)
  await screen.findByText('No saved devices or wiring yet.')
  expect(screen.queryByLabelText('Conduit product for this draft')).toBeNull()
  expect(screen.queryByLabelText('Paper metadata (not calibration)')).toBeNull()
  expect(screen.queryByLabelText('Wire / cable product for this draft')).toBeNull()
  expect(screen.queryByText('Calculation basis')).toBeNull()
  view.rerender(<BOMPanel projectId={2} floorPlanId={5} designer />)
  await waitFor(()=>expect(fetchBOM).toHaveBeenLastCalledWith(2,expect.objectContaining({floorPlanId:5})))
  expect(fetchBOM.mock.calls.at(-1)[1].conduitMaterialId).toBeUndefined()
})
