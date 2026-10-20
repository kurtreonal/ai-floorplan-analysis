/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApplyClientPrices } from './ApplyClientPrices.jsx'
import { listProjectPrices, fetchProjectPrice, ProjectPricingError } from '../../api/projectPricing.js'
import { fetchItemPrices, previewItemPrices, applyItemPrices } from '../../api/itemPricing.js'
vi.mock('../../api/projectPricing.js',async()=>({...await vi.importActual('../../api/projectPricing.js'),listProjectPrices:vi.fn(),fetchProjectPrice:vi.fn()}))
vi.mock('../../api/itemPricing.js',()=>({fetchItemPrices:vi.fn(),previewItemPrices:vi.fn(),applyItemPrices:vi.fn()}))
const rows = [
  {item_key:'a'.repeat(64),item_kind:'device',kind:'device',name:'Duplex outlet',symbol_ids:['device-1'],material_id:5,quantity:1,unit:'piece',unit_price:'10',currency:'PHP',floor_id:2},
  {item_key:'b'.repeat(64),item_kind:'device',kind:'device',name:'Duplex outlet',symbol_ids:['device-2'],material_id:5,quantity:1,unit:'piece',unit_price:'10',currency:'PHP',floor_id:2},
  {item_key:'c'.repeat(64),item_kind:'wire',kind:'path',name:'THHN 3.5 mm²',path_id:'wire-1',material_id:6,quantity:12,unit:'meter',unit_price:'10',currency:'PHP',floor_id:2},
]
const entry = {row_id:'CSV:2',material_id:5,catalog_code:'D1',name:'Duplex outlet',unit:'piece',unit_price:'4',currency:'PHP',excluded:false}
const proposal = {ready:true,preview_token:'f'.repeat(64),affected:[{...rows[0],previous_price:'10',unit_price:'4',previous_currency:'PHP',previous_total:'10',line_total:'4'}],skipped:[]}
beforeEach(()=>{
  listProjectPrices.mockResolvedValue([{id:7,version_number:1,filename:'client.csv'}])
  fetchProjectPrice.mockResolvedValue({id:7,document:{rows:[entry]}})
  fetchItemPrices.mockResolvedValue({items:rows,floors:[2],assignment_version:0})
  previewItemPrices.mockResolvedValue(proposal)
  applyItemPrices.mockResolvedValue({id:8,version_number:1})
})
afterEach(()=>{cleanup();vi.resetAllMocks()})
async function open() {
  fireEvent.click(screen.getByText('Apply client prices to selected items'))
  await waitFor(()=>expect(fetchItemPrices).toHaveBeenCalled())
  fireEvent.change(screen.getByLabelText('Client price list'),{target:{value:'7'}})
  await waitFor(()=>expect(fetchProjectPrice).toHaveBeenCalledWith(15,'7',expect.any(Object)))
  await screen.findByText(/D1 · Duplex outlet/)
  fireEvent.change(screen.getByLabelText('Client price entry'),{target:{value:'CSV:2'}})
}

it('is optional, filters and selects multiple compatible items, previews before atomic application',async()=>{
  const onApplied = vi.fn()
  render(<ApplyClientPrices projectId={15} floorId={2} onApplied={onApplied}/>)
  expect(fetchItemPrices).not.toHaveBeenCalled()
  await open()
  expect(screen.getByLabelText('Apply scope').value).toBe('floor:2')
  expect(screen.getByRole('checkbox',{name:'Price THHN 3.5 mm² wire-1'}).disabled).toBe(true)
  fireEvent.change(screen.getByLabelText('Search saved items'),{target:{value:'device-1'}})
  expect(screen.queryByRole('checkbox',{name:'Price Duplex outlet device-2'})).toBeNull()
  fireEvent.click(screen.getByRole('checkbox',{name:'Price Duplex outlet device-1'}))
  fireEvent.change(screen.getByLabelText('Search saved items'),{target:{value:''}})
  fireEvent.click(screen.getByRole('checkbox',{name:'Price Duplex outlet device-2'}))
  fireEvent.click(screen.getByRole('button',{name:'Preview selected (2)'}))
  await screen.findByRole('region',{name:'Price application preview'})
  expect(applyItemPrices).not.toHaveBeenCalled()
  expect(previewItemPrices.mock.calls[0][1]).toMatchObject({scope:'floor',floor_id:2,mode:'selected',item_keys:[rows[0].item_key,rows[1].item_key]})
  fireEvent.click(screen.getByRole('button',{name:'Apply prices to 1 item'}))
  await screen.findByText('Selected prices applied. Quantities and saved estimates are unchanged.')
  expect(applyItemPrices).toHaveBeenCalledWith(15,expect.objectContaining({preview_token:proposal.preview_token,price_version_id:7}),expect.any(Object))
  expect(onApplied).toHaveBeenCalledOnce()
})

it('requires a scope preview for all existing wiring, reports skipped entries, and invalidates preview on changed inputs',async()=>{
  previewItemPrices.mockResolvedValue({...proposal,skipped:[{item_key:rows[2].item_key,name:'THHN 3.5 mm²',reason:'Different gauge.'}]})
  render(<ApplyClientPrices projectId={15}/>)
  await open()
  fireEvent.click(screen.getByRole('button',{name:'Apply to all existing wirings'}))
  expect(applyItemPrices).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button',{name:'Preview wiring scope'}))
  await screen.findByText('Skipped items (1)')
  expect(previewItemPrices.mock.calls[0][1]).toMatchObject({scope:'project',mode:'all_wiring',item_keys:[]})
  fireEvent.change(screen.getByLabelText('Apply scope'),{target:{value:'floor:2'}})
  expect(screen.queryByRole('region',{name:'Price application preview'})).toBeNull()
})

it('locks an uncertain save and safely retries the same request without a new preview',async()=>{
  applyItemPrices.mockRejectedValueOnce(new ProjectPricingError(503)).mockResolvedValue({id:8,version_number:1})
  render(<ApplyClientPrices projectId={15}/>)
  await open()
  fireEvent.click(screen.getByRole('checkbox',{name:'Price Duplex outlet device-1'}))
  fireEvent.click(screen.getByRole('button',{name:'Preview selected (1)'}))
  await screen.findByRole('region',{name:'Price application preview'})
  fireEvent.click(screen.getByRole('button',{name:'Apply prices to 1 item'}))
  await screen.findByRole('alert')
  expect(screen.getByLabelText('Client price list').closest('fieldset').disabled).toBe(true)
  fireEvent.click(screen.getByRole('button',{name:'Retry price application'}))
  await screen.findByText('Selected prices applied. Quantities and saved estimates are unchanged.')
  expect(applyItemPrices.mock.calls[0][1]).toBe(applyItemPrices.mock.calls[1][1])
  expect(previewItemPrices).toHaveBeenCalledOnce()
})

it('keeps controls visible but unavailable while canvas edits are unsaved and handles no matching items',async()=>{
  const view = render(<ApplyClientPrices projectId={15} disabled/>)
  fireEvent.click(screen.getByText('Apply client prices to selected items'))
  await screen.findByText(/Saved devices and wiring paths/)
  expect(screen.getByLabelText('Client price list').closest('fieldset').disabled).toBe(true)
  view.rerender(<ApplyClientPrices projectId={15}/>)
  await waitFor(()=>expect(fetchItemPrices).toHaveBeenCalled())
  fireEvent.change(screen.getByLabelText('Search saved items'),{target:{value:'not present'}})
  expect(screen.getByText('No matching saved items.')).toBeTruthy()
})

it('offers only device or wiring-path types and keeps both path components searchable',async()=>{
  fetchItemPrices.mockResolvedValue({items:[...rows,{...rows[2],item_key:'d'.repeat(64),item_kind:'conduit',material_kind:'conduit',name:'PVC 20 mm',material_id:8}],floors:[2],assignment_version:0})
  render(<ApplyClientPrices projectId={15}/>)
  await open()
  const types=screen.getByLabelText('Item type')
  expect([...types.options].map(o=>o.textContent)).toEqual(['All types','Devices','Wiring paths'])
  fireEvent.change(types,{target:{value:'path'}})
  expect(screen.getByRole('checkbox',{name:'Price THHN 3.5 mm² wire-1'})).toBeTruthy()
  expect(screen.getByRole('checkbox',{name:'Price PVC 20 mm wire-1'})).toBeTruthy()
  expect(screen.queryByRole('checkbox',{name:'Price Duplex outlet device-1'})).toBeNull()
  fireEvent.change(types,{target:{value:'device'}})
  expect(screen.queryByRole('checkbox',{name:'Price THHN 3.5 mm² wire-1'})).toBeNull()
})
