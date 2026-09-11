import { afterEach, expect, it, vi } from 'vitest'
import { listAdminLegends, saveAdminLegend } from './adminLegends.js'
afterEach(() => vi.unstubAllGlobals())

it('uses authenticated admin endpoints and reports backend denial', async () => {
  const fetch = vi.fn().mockResolvedValue({ok:false,status:403})
  vi.stubGlobal('fetch', fetch)
  await expect(listAdminLegends()).rejects.toThrow('Only an Admin')
  expect(fetch.mock.calls[0][1].credentials).toBe('include')
})

it('rejects malformed responses and invalid class identities', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ok:true,json:async()=>[{id:1,class_id:0,name:'Missing status'}]}))
  await expect(listAdminLegends()).rejects.toThrow('invalid result')
  expect(() => saveAdminLegend({class_id:-1,name:'Test',is_active:true})).toThrow('Invalid legend fields')
})
