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
  if (record.result?.algorithm === 'greedy_shared_service_tree_v1') {
    validateCircuit(record, projectId, record.configuration, 'saved_planning')
    return record
  }
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

export async function previewCircuit(projectId, configuration, { signal } = {}) {
  return circuitRequest(projectId, configuration, signal, false)
}

export async function saveCircuit(projectId, configuration, { signal } = {}) {
  return circuitRequest(projectId, configuration, signal, true)
}

async function circuitRequest(projectId, configuration, signal, save) {
  const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/routes`, {
    method: 'POST', credentials: 'include', signal,
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(configuration),
  })
  const record = await response.json().catch(() => null)
  if (!response.ok) {
    const code = record?.detail?.error?.code
    const failure = new Error(typeof code === 'string' && /^[A-Z_]+$/.test(code) ? code : 'Circuit preview is unavailable.')
    failure.status = response.status
    throw failure
  }
  if (response.status !== (save ? 201 : 200)) throw new Error('Invalid circuit response status.')
  validateCircuit(record, projectId, configuration, save ? 'saved_planning' : 'preview_not_saved')
  return record
}

function validateCircuit(record, projectId, configuration, status) {
  const result = record?.result
  const metric = (n) => Number.isFinite(n) && n >= 0
  const point = (p) => p && Number.isSafeInteger(p.floor_id) && p.floor_id > 0
    && [p.x, p.y, p.elevation_meters].every(Number.isFinite)
  const lengths = (value) => value && ['horizontal_meters', 'vertical_meters', 'total_meters'].every((key) => metric(value[key]))
    && Math.abs(value.total_meters - value.horizontal_meters - value.vertical_meters) < 1e-6
  const expected = new Set(configuration.targets.map((target) => `${target.floor_id}:${target.symbol_id}`))
  if (record?.project_id !== projectId || typeof record.stale !== 'boolean'
    || (status === 'preview_not_saved' && record.stale)
    || (status === 'saved_planning' && (!Number.isSafeInteger(record.id) || record.id <= 0
      || !Number.isSafeInteger(record.version_number) || record.version_number <= 0
      || record.configuration?.intent !== 'save_planning_circuit' || !record.configuration.request_id))
    || !record.layout_versions || !Object.values(record.layout_versions).every((id) => Number.isSafeInteger(id) && id > 0)
    || record.configuration?.circuit_id !== configuration.circuit_id || !Array.isArray(record.configuration?.floors)
    || result?.circuit_id !== configuration.circuit_id
    || !['ceiling_service', 'underground'].includes(result.installation_method)
    || result.installation_method !== configuration.installation_method
    || (result.installation_method === 'underground' && (configuration.floor_passages_confirmed !== true
      || record.configuration.floor_passages_confirmed !== true))
    || result.provenance !== 'generated' || result.status !== status
    || result.algorithm !== 'greedy_shared_service_tree_v1' || result.optimality !== 'graph_heuristic_not_global_optimum'
    || !lengths(result) || !Array.isArray(result.segments) || !result.segments.length
    || result.segments.some((segment) => !point(segment.start) || !point(segment.end)
      || !['ceiling_service', 'wall_rise', 'wall_drop', 'riser', 'underground', 'underground_rise', 'underground_drop'].includes(segment.kind)
      || (segment.kind.startsWith('underground') && result.installation_method !== 'underground')
      || !metric(segment.horizontal_meters) || !metric(segment.vertical_meters))
    || !Array.isArray(result.branches) || result.branches.length !== expected.size
    || new Set(result.branches.map((branch) => `${branch.floor_id}:${branch.symbol_id}`)).size !== expected.size
    || result.branches.some((branch) => !expected.has(`${branch.floor_id}:${branch.symbol_id}`) || !lengths(branch)
      || !Array.isArray(branch.points) || !branch.points.length || branch.points.some((p) => !point(p))
      || !Array.isArray(branch.segment_indices) || branch.segment_indices.some((index) => !Number.isSafeInteger(index)
        || index < 0 || index >= result.segments.length))) {
    throw new Error('Invalid circuit preview response.')
  }
}
