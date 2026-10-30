import { API_BASE_URL } from './auth.js'

export async function createAdminCatalogItem(data){
  const response=await fetch(`${API_BASE_URL}/api/admin/materials`,{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})
  const body=await response.json().catch(()=>null)
  if(!response.ok)throw new Error(body?.detail?.error?.message || (response.status===403?'Only Admin can add catalog items.':'Check the item code, product, unit and purchase price.'))
  return body
}

export async function adminMaterialCatalog({signal}={}){
  const response=await fetch(`${API_BASE_URL}/api/admin/materials`,{credentials:'include',signal})
  if(!response.ok)throw new Error('Material prices could not be loaded. Check your session and retry.')
  const rows=await response.json()
  if(!Array.isArray(rows))throw new Error('Material prices are unavailable.')
  return rows
}

export async function saveAdminMaterialPrice(material,data){
  const response=await fetch(`${API_BASE_URL}/api/admin/materials/${material.id}/price`,{method:'PUT',credentials:'include',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({...data,expected_revision:material.revision})})
  if(!response.ok)throw new Error(response.status===409 ? 'Price changed. Reload before saving again.':'Price was not saved. Reload and try again.')
}

export async function adminAssemblies(data,materialId,{signal}={}){
  const response=await fetch(`${API_BASE_URL}/api/admin/material-assemblies${materialId?`/${materialId}`:''}`,{
    credentials:'include',signal,method:data?(materialId?'PUT':'POST'):'GET',
    ...(data?{headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{})})
  const body=await response.json().catch(()=>null)
  if(!response.ok)throw new Error(typeof body?.detail==='string'?body.detail:'Device assemblies are unavailable. Reload and retry.')
  if(!body||!Array.isArray(body.assemblies))throw new Error('Device assemblies are unavailable.')
  return body
}

export async function downloadAssemblyPriceList(){
  const response=await fetch(`${API_BASE_URL}/api/admin/material-assemblies/price-list.csv`,{credentials:'include',cache:'no-store'})
  if(!response.ok)throw new Error('Price list download is unavailable. Check your session and retry.')
  return response.blob()
}

export async function importMaterialPrices(file, selection, { signal } = {}) {
  const form = new FormData()
  form.append('file', file)
  if (selection) form.append('selection', JSON.stringify(selection))
  const response = await fetch(`${API_BASE_URL}/api/admin/materials/import/${selection ? 'apply' : 'preview'}`, {
    method: 'POST', credentials: 'include', signal, body: form, headers: { Accept: 'application/json' },
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new Error(response.status === 403 ? 'Only an Admin can import material prices.'
    : response.status === 401 ? 'Sign in again to import prices.' : body?.detail?.error?.message || 'Import unavailable. Preview again before retrying.')
  if (!body || !/^[a-f0-9]{64}$/.test(body.file_sha256) || (!selection && (!Array.isArray(body.rows) || !Array.isArray(body.issues)))
    || (selection && !['created', 'updated', 'unchanged'].every(key => Number.isInteger(body[key]) && body[key] >= 0))) {
    throw new Error('Invalid import response. No changes are confirmed.')
  }
  return body
}
