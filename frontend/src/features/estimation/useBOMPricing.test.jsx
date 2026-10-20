/* @vitest-environment jsdom */
import {act,cleanup,renderHook,waitFor} from '@testing-library/react'
import {afterEach,it,expect,vi} from 'vitest'
import {useBOMPricing} from './useBOMPricing.js'
import {listProjectPrices,fetchProjectPrice} from '../../api/projectPricing.js'
import {fetchItemPrices,previewItemPrices,applyItemPrices} from '../../api/itemPricing.js'
vi.mock('../../api/projectPricing.js',()=>({listProjectPrices:vi.fn(),fetchProjectPrice:vi.fn(),previewProjectPrices:vi.fn(),applyProjectPrices:vi.fn()}))
vi.mock('../../api/itemPricing.js',()=>({fetchItemPrices:vi.fn(),previewItemPrices:vi.fn(),applyItemPrices:vi.fn()}))
afterEach(()=>{cleanup();vi.resetAllMocks()})

async function ready(){
  const row={kind:'device',name:'Outlet',unit:'piece',item_key:'a'.repeat(64),material_id:3,compatible_prices:['Quote:2']}
  listProjectPrices.mockResolvedValue([{id:7}]);fetchProjectPrice.mockResolvedValue({id:7,document:{rows:[{row_id:'Quote:2',material_id:3,excluded:false}]}})
  fetchItemPrices.mockResolvedValue({items:[row],floors:[1]});previewItemPrices.mockResolvedValue({ready:true,preview_token:'a'.repeat(64),affected:[row],skipped:[]})
  const hook=renderHook(({projectId})=>useBOMPricing({projectId,disabled:false}),{initialProps:{projectId:1}})
  await act(async()=>hook.result.current.existing())
  await waitFor(()=>expect(hook.result.current.stage).toBe('versions'))
  await act(async()=>hook.result.current.chooseVersion(7))
  await waitFor(()=>expect(hook.result.current.active).toBe(true))
  act(()=>hook.result.current.selectVisible())
  await act(async()=>hook.result.current.requestPreview())
  await waitFor(()=>expect(hook.result.current.previewResult?.ready).toBe(true))
  return hook
}
it('retries an uncertain application with the identical request id and payload',async()=>{
  const hook=await ready()
  applyItemPrices.mockRejectedValueOnce(new Error('Network interrupted')).mockResolvedValueOnce({version_number:1})
  await act(async()=>hook.result.current.apply())
  await waitFor(()=>expect(hook.result.current.uncertain).toBe(true))
  act(()=>hook.result.current.finish())
  expect(hook.result.current.active).toBe(true)
  await act(async()=>hook.result.current.retry())
  await waitFor(()=>expect(hook.result.current.uncertain).toBe(false))
  expect(applyItemPrices.mock.calls[0][1]).toEqual(applyItemPrices.mock.calls[1][1])
})
it('allows cancellation and fresh preview after a definitive stale-input rejection',async()=>{
  const hook=await ready()
  applyItemPrices.mockRejectedValue(Object.assign(new Error('Preview again'),{status:409}))
  await act(async()=>hook.result.current.apply())
  await waitFor(()=>expect(hook.result.current.error).toBe('Preview again'))
  expect(hook.result.current.previewResult).toBeNull()
  act(()=>hook.result.current.finish())
  expect(hook.result.current.stage).toBe('idle')
})
it('does not carry pending item writes into a different project',async()=>{
  const hook=await ready()
  applyItemPrices.mockRejectedValue(new Error('Network interrupted'))
  await act(async()=>hook.result.current.apply())
  await waitFor(()=>expect(hook.result.current.uncertain).toBe(true))
  hook.rerender({projectId:2})
  expect(hook.result.current.stage).toBe('idle')
  await act(async()=>hook.result.current.existing())
  expect(listProjectPrices).toHaveBeenLastCalledWith(2,expect.anything())
})
