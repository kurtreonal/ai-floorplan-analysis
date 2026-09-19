import { API_BASE_URL } from './auth.js'

export async function routingRequest(projectId, { configuration, signal } = {}) {
  const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/routes`, {
    method: configuration ? 'POST' : 'GET', credentials: 'include', signal,
    headers: { Accept: 'application/json', ...(configuration ? { 'Content-Type': 'application/json' } : {}) },
    ...(configuration ? { body: JSON.stringify(configuration) } : {}),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const code = body?.detail?.error?.code
    throw new Error(typeof code === 'string' && /^[A-Z_]+$/.test(code) ? code : 'Routing is unavailable.')
  }
  const record = await response.json()
  if (record === null) return null
  const pointValid = (p) => p && Number.isSafeInteger(p.floor_id) && [p.x, p.y, p.elevation_meters].every(Number.isFinite)
  if (record.project_id !== projectId || !Number.isSafeInteger(record.version_number)
    || !record.layout_versions || !Array.isArray(record.configuration?.floors)
    || record.result?.provenance !== 'generated' || !Array.isArray(record.result.segments)
    || ![record.result.horizontal_meters, record.result.vertical_meters, record.result.total_meters].every((n) => Number.isFinite(n) && n >= 0)
    || record.result.segments.some((s) => !pointValid(s.start) || !pointValid(s.end))) {
    throw new Error('Invalid saved routing response.')
  }
  return record
}
