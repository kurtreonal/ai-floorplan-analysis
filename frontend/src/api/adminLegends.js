import { API_BASE_URL } from './auth.js'

function valid(record) {
  return record && Number.isSafeInteger(record.id) && record.id > 0
    && Number.isSafeInteger(record.class_id) && record.class_id >= 0
    && record.class_id <= 2147483647 && typeof record.name === 'string'
    && record.name.trim().length > 0 && record.name.length <= 255
    && typeof record.is_active === 'boolean'
}

async function request(method, body, id, {signal}={}) {
  const response = await fetch(`${API_BASE_URL}/api/admin/symbol-legends${id === undefined ? '' : `/${id}`}`, {
    method, credentials: 'include',signal, headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
  if (!response.ok) {
    const messages = {401: 'Your session expired. Sign in again.', 403: 'Only an Admin can manage symbol legends.', 409: 'That legend already exists or the catalog changed. Search All statuses and edit the existing entry, or reload before adding it.', 422: 'Check the class number and name.'}
    throw new Error(messages[response.status] || 'Legend service unavailable. Reload the catalog before retrying a save.')
  }
  const result = await response.json()
  if (method === 'GET' ? !Array.isArray(result) || !result.every(valid) : !valid(result)) throw new Error('The legend service returned an invalid result. Reload before retrying.')
  return result
}

export const listAdminLegends = (options) => request('GET',undefined,undefined,options)
export const importTrainedLegends = () => importCatalog('trained')
export const importApprovedPdfLegends = () => importCatalog('approved-pdf')
async function importCatalog(catalog) {
  const suffix = catalog === 'approved-pdf' ? '?catalog=approved-pdf' : ''
  const response = await fetch(`${API_BASE_URL}/api/admin/symbol-legends/import-trained${suffix}`, {
    method: 'POST', credentials: 'include', headers: { Accept: 'application/json' },
  })
  if (!response.ok) throw new Error(response.status === 403
    ? 'Only an Admin in local development can import legend catalogs.'
    : `${catalog === 'approved-pdf' ? 'Authorized PDF' : 'Verified training'} legends could not be imported. Reload before retrying.`)
  const result = await response.json()
  if (!Array.isArray(result) || !(catalog === 'approved-pdf' ? [40] : [56, 60, 80]).includes(result.length) || !result.every(valid)
    || new Set(result.map((row) => row.id)).size !== result.length
    || new Set(result.map((row) => row.class_id)).size !== result.length
    || new Set(result.map((row) => row.name)).size !== result.length) {
    throw new Error('The training legend service returned an invalid result. Reload before retrying.')
  }
  result.forEach(row=>window.dispatchEvent(new CustomEvent('ved:legend-artwork-changed',{detail:row.id})))
  return result
}
export function saveAdminLegend(body, id) {
  if (!Number.isSafeInteger(body.class_id) || body.class_id < 0 || body.class_id > 2147483647
    || typeof body.name !== 'string' || !body.name.trim() || body.name.length > 255
    || typeof body.is_active !== 'boolean' || (id !== undefined && (!Number.isSafeInteger(id) || id < 1))) throw new Error('Invalid legend fields.')
  return request(id === undefined ? 'POST' : 'PUT', body, id)
}

export async function uploadLegendArtwork(id, file, ids=[id]) {
  const body = new FormData(); body.set('image', file)
  ids.forEach(value=>body.append('legend_ids',String(value)))
  const response = await fetch(`${API_BASE_URL}/api/admin/symbol-legends/${id}/artwork`, { method: 'POST', credentials: 'include', body })
  if (!response.ok) throw new Error('Legend saved, but the image upload failed. Use PNG, JPEG or WebP up to 2 MB and retry from Edit.')
  ids.forEach(value=>window.dispatchEvent(new CustomEvent('ved:legend-artwork-changed', { detail: value })))
  return response.json()
}

export async function listLegendReferenceImages({signal}={}){
  const response=await fetch(`${API_BASE_URL}/api/admin/symbol-legends/reference-images`,{credentials:'include',signal})
  if(!response.ok)throw new Error('PEC images are unavailable. You can upload your own symbol image.')
  const rows=await response.json()
  if(!Array.isArray(rows)||!rows.every(row=>/^R[0-9_]+-(as_shown|wall|ceiling)$/.test(row.id) && typeof row.label==='string'))throw new Error('PEC image list is unavailable.')
  return rows
}

export async function saveLegendReferenceImage(id,referenceId,ids=[id]){
  const response=await fetch(`${API_BASE_URL}/api/admin/symbol-legends/${id}/reference-artwork`,{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({reference_id:referenceId,legend_ids:ids})})
  if(!response.ok)throw new Error('Legend saved, but its PEC image was not applied. Reopen Edit and choose the symbol again.')
  ids.forEach(value=>window.dispatchEvent(new CustomEvent('ved:legend-artwork-changed',{detail:value})))
  return response.json()
}

export async function setLegendAvailability(ids,isActive){
  const response=await fetch(`${API_BASE_URL}/api/admin/symbol-legends/availability`,{method:'PUT',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({legend_ids:ids,is_active:isActive})})
  if(!response.ok)throw new Error('Availability was not changed. Reload the legend list and retry.')
  const rows=await response.json()
  if(!Array.isArray(rows)||!rows.every(valid))throw new Error('Reload the legend list to check availability.')
  return rows
}
