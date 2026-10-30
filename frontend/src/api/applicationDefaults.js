import { API_BASE_URL } from './auth.js'

export async function applicationDefaults(settings=null,signal) {
  const response=await fetch(`${API_BASE_URL}/api/${settings ? 'admin/':''}application-defaults`,{
    credentials:'include',signal,...(settings ? {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(settings)}:{})})
  if(!response.ok)throw new Error(response.status===403 ? 'Only an Admin can change shared defaults.':response.status===409 ? 'Defaults changed. Reload and try again.':'Defaults could not be saved or loaded. Check settings storage and retry.')
  const record=await response.json()
  if(!record?.settings || !Number.isInteger(record.revision) || typeof record.writable!=='boolean')throw new Error('Shared settings are unavailable. Reload and try again.')
  return record
}
