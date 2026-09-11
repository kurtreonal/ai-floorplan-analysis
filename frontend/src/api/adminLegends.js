import { API_BASE_URL } from './auth.js'

function valid(record) {
  return record && Number.isSafeInteger(record.id) && record.id > 0
    && Number.isSafeInteger(record.class_id) && record.class_id >= 0
    && record.class_id <= 2147483647 && typeof record.name === 'string'
    && record.name.trim().length > 0 && record.name.length <= 255
    && typeof record.is_active === 'boolean'
}

async function request(method, body, id) {
  const response = await fetch(`${API_BASE_URL}/api/admin/symbol-legends${id === undefined ? '' : `/${id}`}`, {
    method, credentials: 'include', headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
  if (!response.ok) {
    const messages = {401: 'Your session expired. Sign in again.', 403: 'Only an Admin can manage symbol legends.', 409: 'That class number or name already exists. Reload the catalog.', 422: 'Check the class number and name.'}
    throw new Error(messages[response.status] || 'Legend service unavailable. Reload the catalog before retrying a save.')
  }
  const result = await response.json()
  if (method === 'GET' ? !Array.isArray(result) || !result.every(valid) : !valid(result)) throw new Error('The legend service returned an invalid result. Reload before retrying.')
  return result
}

export const listAdminLegends = () => request('GET')
export function saveAdminLegend(body, id) {
  if (!Number.isSafeInteger(body.class_id) || body.class_id < 0 || body.class_id > 2147483647
    || typeof body.name !== 'string' || !body.name.trim() || body.name.length > 255
    || typeof body.is_active !== 'boolean' || (id !== undefined && (!Number.isSafeInteger(id) || id < 1))) throw new Error('Invalid legend fields.')
  return request(id === undefined ? 'POST' : 'PUT', body, id)
}
