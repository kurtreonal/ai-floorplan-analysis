/* @vitest-environment jsdom */
import {act,cleanup,renderHook,waitFor} from '@testing-library/react'
import {afterEach,it,expect,vi} from 'vitest'
import {useBOMPricing} from './useBOMPricing.js'
import {uploadAutomaticPrices,listProjectPrices} from '../../api/projectPricing.js'
vi.mock('../../api/projectPricing.js',()=>({listProjectPrices:vi.fn(),uploadAutomaticPrices:vi.fn()}))
afterEach(()=>{cleanup();vi.resetAllMocks()})
const result={price_version_id:7,applied:3,skipped:[],skipped_rows:[]}
it('uploads and applies without a review/selection stage and refreshes once',async()=>{
  const onApplied=vi.fn(),onVersionsChange=vi.fn()
  uploadAutomaticPrices.mockResolvedValue(result);listProjectPrices.mockResolvedValue([])
  const hook=renderHook(()=>useBOMPricing({projectId:1,floorId:2,disabled:false,onApplied,onVersionsChange}))
  const file=new File(['test'],'client.csv')
  await act(async()=>hook.result.current.uploaded(file))
  await waitFor(()=>expect(hook.result.current.result).toEqual(result))
  expect(uploadAutomaticPrices).toHaveBeenCalledOnce()
  expect(uploadAutomaticPrices).toHaveBeenCalledWith(1,file,expect.objectContaining({floorId:2,requestId:expect.any(String)}))
  expect(onApplied).toHaveBeenCalledOnce();expect(hook.result.current.active).toBe(false)
})
it('retries an uncertain upload with identical file, scope and request id',async()=>{
  uploadAutomaticPrices.mockRejectedValueOnce(new Error('Network interrupted')).mockResolvedValueOnce(result)
  const hook=renderHook(()=>useBOMPricing({projectId:1,floorId:2,disabled:false}))
  await act(async()=>hook.result.current.uploaded(new File(['test'],'client.csv')))
  await waitFor(()=>expect(hook.result.current.uncertain).toBe(true))
  await act(async()=>hook.result.current.retry())
  await waitFor(()=>expect(hook.result.current.result).toEqual(result))
  expect(uploadAutomaticPrices.mock.calls[0].slice(0,2)).toEqual(uploadAutomaticPrices.mock.calls[1].slice(0,2))
  expect(uploadAutomaticPrices.mock.calls[0][2].requestId).toBe(uploadAutomaticPrices.mock.calls[1][2].requestId)
})
it('allows a new file after a definitive validation error',async()=>{
  uploadAutomaticPrices.mockRejectedValueOnce(Object.assign(new Error('Missing currency'),{status:422})).mockResolvedValueOnce(result)
  const hook=renderHook(()=>useBOMPricing({projectId:1,disabled:false}))
  await act(async()=>hook.result.current.uploaded(new File(['bad'],'bad.csv')))
  await waitFor(()=>expect(hook.result.current.error).toBe('Missing currency'))
  await act(async()=>hook.result.current.uploaded(new File(['good'],'good.csv')))
  await waitFor(()=>expect(hook.result.current.result).toEqual(result))
})
it('does not retry a previous project upload after navigation',async()=>{
  uploadAutomaticPrices.mockRejectedValue(new Error('Network interrupted'))
  const hook=renderHook(({projectId})=>useBOMPricing({projectId,disabled:false}),{initialProps:{projectId:1}})
  await act(async()=>hook.result.current.uploaded(new File(['test'],'client.csv')))
  await waitFor(()=>expect(hook.result.current.uncertain).toBe(true))
  hook.rerender({projectId:2})
  await act(async()=>hook.result.current.retry())
  expect(uploadAutomaticPrices).toHaveBeenCalledOnce();expect(hook.result.current.uncertain).toBe(false)
})
