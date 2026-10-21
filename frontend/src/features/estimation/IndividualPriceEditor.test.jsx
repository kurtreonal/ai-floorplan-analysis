/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { fetchItemPrices,saveIndividualPrices } from '../../api/itemPricing.js'
import { IndividualPriceEditor } from './IndividualPriceEditor.jsx'
vi.mock('../../api/itemPricing.js',()=>({fetchItemPrices:vi.fn(),saveIndividualPrices:vi.fn()}))
afterEach(()=>{cleanup();vi.resetAllMocks()})
const row={item_key:'a'.repeat(64),kind:'device',name:'Lamp',symbol_ids:['symbol-0001'],floor_plan_id:3,unit:'piece',unit_price:'25',currency:'PHP'}

it('opens only on request, saves one individual price and preserves zero overrides',async()=>{
  fetchItemPrices.mockResolvedValue({assignment_version:2,items:[row,{...row,item_key:'b'.repeat(64),floor_plan_id:4}],floors:[2]})
  saveIndividualPrices.mockResolvedValue({id:3,version_number:3})
  const changed=vi.fn()
  render(<IndividualPriceEditor projectId={1} floorPlanId={3} onSaved={changed}/>)
  expect(fetchItemPrices).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button',{name:'Edit prices'}))
  const price=await screen.findByLabelText('Price '+row.item_key)
  expect(screen.getByRole('dialog')).toBeTruthy()
  expect(screen.queryByLabelText('Price '+'b'.repeat(64))).toBeNull()
  fireEvent.change(price,{target:{value:'0'}})
  fireEvent.click(screen.getByRole('button',{name:'Save prices'}))
  await waitFor(()=>expect(changed).toHaveBeenCalledOnce())
  expect(saveIndividualPrices).toHaveBeenCalledWith(1,expect.objectContaining({expected_version:2,items:[{item_key:row.item_key,unit_price:'0',currency:'PHP'}]}),expect.anything())
  expect(screen.queryByRole('dialog')).toBeNull()
})

it('filters and cancels without saving, and retries uncertain saves with the same identity',async()=>{
  fetchItemPrices.mockResolvedValue({assignment_version:0,items:[row],floors:[2]})
  saveIndividualPrices.mockRejectedValueOnce(Object.assign(new Error('Unavailable'),{status:503})).mockResolvedValue({id:1,version_number:1})
  render(<IndividualPriceEditor projectId={1}/>)
  fireEvent.click(screen.getByRole('button',{name:'Edit prices'}))
  fireEvent.change(await screen.findByLabelText('Price '+row.item_key),{target:{value:'30'}})
  fireEvent.click(screen.getByRole('button',{name:'Save prices'}))
  await screen.findByRole('alert')
  fireEvent.click(screen.getByRole('button',{name:'Retry save'}))
  await waitFor(()=>expect(saveIndividualPrices).toHaveBeenCalledTimes(2))
  expect(saveIndividualPrices.mock.calls[0][1]).toEqual(saveIndividualPrices.mock.calls[1][1])
  await waitFor(()=>expect(screen.queryByRole('dialog')).toBeNull())
  fireEvent.click(screen.getByRole('button',{name:'Edit prices'}))
  await screen.findByLabelText('Price '+row.item_key)
  fireEvent.change(screen.getByLabelText('Find device or path'),{target:{value:'unmatched'}})
  expect(screen.getByText('No matching saved items.')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Cancel'}))
  expect(saveIndividualPrices).toHaveBeenCalledTimes(2)
})
