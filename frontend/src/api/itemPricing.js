import { API_BASE_URL } from './auth.js'
import { ProjectPricingError } from './projectPricing.js'

async function request(projectId, suffix, body, options = {}) {
  if (!Number.isSafeInteger(projectId) || projectId <= 0) throw new ProjectPricingError(422)
  let response
  try {
    const query=!suffix && options.priceVersionId ? `?price_version_id=${encodeURIComponent(options.priceVersionId)}`:''
    response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/client-pricing/item-assignments${suffix}${query}`, {
      credentials: 'include', method: body ? 'POST' : 'GET', signal: options.signal,
      headers: { Accept: 'application/json', ...(body ? {'Content-Type':'application/json'} : {}) },
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ProjectPricingError()
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    if (response.status === 401) window.location.replace('#/signin?reason=session-expired')
    throw new ProjectPricingError(response.status, response.status >= 500 ? undefined : data?.detail?.error?.message)
  }
  const data = await response.json()
  const valid = suffix === '' ? Array.isArray(data.items) && data.items.length <= 10000 && Array.isArray(data.floors)
    : suffix === '/preview' ? Array.isArray(data.affected) && Array.isArray(data.skipped) && typeof data.preview_token === 'string'
      : Number.isSafeInteger(data.id) && Number.isSafeInteger(data.version_number)
  if (!valid) throw new ProjectPricingError(0, 'Reload the saved item prices and try again.')
  return data
}

export const fetchItemPrices = (id, options) => request(id, '', null, options)
export const previewItemPrices = (id, selection, options) => request(id, '/preview', selection, options)
export const applyItemPrices = (id, selection, options) => request(id, '/apply', selection, options)
export const saveIndividualPrices = (id, selection, options) => request(id, '/prices', selection, options)
