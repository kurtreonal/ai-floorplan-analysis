import { API_BASE_URL } from './auth.js'

export class ProjectPricingError extends Error {
  constructor(status = 0, message = 'Client pricing is unavailable. Try again.') {
    super(message)
    this.name = 'ProjectPricingError'
    this.status = status
  }
}

async function request(projectId, suffix, { signal, file, selection, sheet, headerRow, estimateId, usage } = {}) {
  if (!Number.isSafeInteger(projectId) || projectId <= 0) throw new ProjectPricingError(422)
  let body
  if (file) {
    body = new FormData()
    body.append('file', file)
    if (selection) body.append('selection', JSON.stringify(selection))
    if (sheet) body.append('sheet', sheet)
    if (headerRow) body.append('header_row', String(headerRow))
    if (usage) body.append('usage', usage)
  }
  const query = estimateId ? '?estimate_id=' + encodeURIComponent(estimateId) : ''
  let response
  try {
    response = await fetch(API_BASE_URL + '/api/projects/' + projectId + '/client-pricing' + suffix + query,
      { credentials: 'include', method: file ? 'POST' : 'GET', signal, headers: { Accept: 'application/json' }, body })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ProjectPricingError()
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    if (response.status === 401) window.location.replace('#/signin?reason=session-expired')
    const message = response.status >= 500 ? undefined : data?.detail?.error?.message
    throw new ProjectPricingError(response.status, typeof message === 'string' && message.length <= 350 ? message : undefined)
  }
  let data
  try { data = await response.json() } catch { throw new ProjectPricingError() }
  const version = row => row?.project_id === projectId && Number.isSafeInteger(row.id) && row.id > 0
    && Number.isSafeInteger(row.version_number) && row.version_number > 0 && typeof row.filename === 'string'
  const valid = suffix === '' ? Array.isArray(data) && data.every(version)
    : suffix === '/inspect' ? Array.isArray(data?.sheets) && Array.isArray(data.columns) && typeof data.sheet === 'string'
      : suffix === '/preview' ? Array.isArray(data?.document?.rows) && data.document.rows.length <= 1000
        && Array.isArray(data.materials) && typeof data.ready === 'boolean' && typeof data.preview_token === 'string'
        : version(data) && (suffix === '/apply' || Array.isArray(data.document?.rows))
  if (!valid) throw new ProjectPricingError(0, 'The client pricing response is invalid. Reload and try again.')
  return data
}

export const listProjectPrices = (id, options) => request(id, '', options)
export const fetchProjectPrice = (id, version, options) => request(id, '/' + encodeURIComponent(version), options)
export const inspectProjectPrices = (id, file, options) => request(id, '/inspect', { ...options, file })
export const previewProjectPrices = (id, file, selection, options) => request(id, '/preview', { ...options, file, selection })
export const applyProjectPrices = (id, file, selection, options) => request(id, '/apply', { ...options, file, selection })
