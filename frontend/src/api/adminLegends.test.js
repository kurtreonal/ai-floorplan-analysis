import { afterEach, expect, it, vi } from 'vitest'
import { importTrainedLegends, importApprovedPdfLegends, listAdminLegends, saveAdminLegend } from './adminLegends.js'
afterEach(() => vi.unstubAllGlobals())

it('accepts a complete 80-entry trained head independently of the 40-entry authored catalog', async () => {
  const entries=Array.from({length:80},(_,i)=>({id:i+1,class_id:i+100,name:`Fixture [drawing:L${i}]`,is_active:true}))
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>entries}))
  expect(await importTrainedLegends()).toEqual(entries)
  await expect(importApprovedPdfLegends()).rejects.toThrow('invalid result')
})

it('imports exactly 40 PDF entries using session authority and rejects incomplete/duplicate results', async () => {
  const entries = Array.from({ length: 40 }, (_, i) => ({ id: i + 1, class_id: i + 100,
    name: `Fixture [pdf-76f411c60b6d:p1:L${i}]`, is_active: true }))
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => entries })
  vi.stubGlobal('fetch', fetch)
  expect(await importApprovedPdfLegends()).toEqual(entries)
  expect(fetch.mock.calls[0][0]).toMatch(/\/import-trained\?catalog=approved-pdf$/)
  expect(fetch.mock.calls[0][1]).toMatchObject({ method: 'POST', credentials: 'include' })
  for (const broken of [entries.slice(1), [...entries.slice(0, -1), entries[0]]]) {
    fetch.mockResolvedValue({ ok: true, json: async () => broken })
    await expect(importApprovedPdfLegends()).rejects.toThrow('invalid result')
  }
})

it('imports only through the authenticated admin endpoint with a complete catalog response', async () => {
  const entries = Array.from({length:56}, (_,i) => ({id:i+10,class_id:i+100,name:`Fixture [sheet-${i}:L1]`,is_active:true}))
  const fetch = vi.fn().mockResolvedValue({ok:true,json:async()=>entries})
  vi.stubGlobal('fetch', fetch)
  expect(await importTrainedLegends()).toEqual(entries)
  expect(fetch.mock.calls[0][0]).toMatch(/\/api\/admin\/symbol-legends\/import-trained$/)
  expect(fetch.mock.calls[0][1]).toMatchObject({method:'POST',credentials:'include'})
  fetch.mockResolvedValue({ok:true,json:async()=>entries.slice(1)})
  await expect(importTrainedLegends()).rejects.toThrow('invalid result')
  fetch.mockResolvedValue({ok:false,status:403})
  await expect(importTrainedLegends()).rejects.toThrow('Only an Admin')
})

it('accepts the complete 60-entry extension but rejects duplicates or missing entries', async () => {
  const entries = Array.from({length:60}, (_,i) => ({id:i+10,class_id:i+100,name:`Fixture [drawing:L${i}]`,is_active:true}))
  const fetch = vi.fn().mockResolvedValue({ok:true,json:async()=>entries})
  vi.stubGlobal('fetch',fetch)
  expect(await importTrainedLegends()).toEqual(entries)
  fetch.mockResolvedValue({ok:true,json:async()=>entries.slice(1)})
  await expect(importTrainedLegends()).rejects.toThrow('invalid result')
  fetch.mockResolvedValue({ok:true,json:async()=>[...entries.slice(0,-1),entries[0]]})
  await expect(importTrainedLegends()).rejects.toThrow('invalid result')
})

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
