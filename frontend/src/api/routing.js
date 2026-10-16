import { API_BASE_URL } from './auth.js'

const missingAlgorithms = ['assigned_missing_device_astar_v1', 'assigned_missing_device_astar_v2', 'assigned_missing_device_astar_v3']
const circuitAlgorithms = ['greedy_shared_service_tree_v1', ...missingAlgorithms]

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
  if (circuitAlgorithms.includes(record.result?.algorithm)) {
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
  const missing = missingAlgorithms.includes(result?.algorithm)
  if (!Array.isArray(result?.branches)
    || (result.skipped_targets != null && !Array.isArray(result.skipped_targets))
    || (result.unresolved_targets != null && !Array.isArray(result.unresolved_targets))) {
    throw new Error('Invalid circuit preview response.')
  }
  const issues = [...(result?.skipped_targets ?? []), ...(result?.unresolved_targets ?? [])]
  const assignments = configuration.observed_route_assignments ?? []
  const reused = result?.reused_observed_routes ?? []
  const takeoff = result?.planning_takeoff
  const assignmentKey = item => `${item.floor_id}:${item.route_id}`
  const covered = [...(result?.branches ?? []), ...issues].map((item) => `${item.floor_id}:${item.symbol_id}`)
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
    || (takeoff != null && (takeoff.basis !== 'selected_network_uniform_conductors_planning_only'
      || !['observed_meters','generated_meters','horizontal_meters','vertical_meters','conduit_meters'].every(key=>metric(takeoff[key]))
      || Math.abs(takeoff.conduit_meters-takeoff.horizontal_meters-takeoff.vertical_meters)>1e-6
      || takeoff.conductor_count !== (configuration.conductor_count ?? null)
      || (takeoff.conductor_count == null ? takeoff.one_conductor_meters !== null || takeoff.total_conductor_meters !== null
        : !Number.isSafeInteger(takeoff.conductor_count) || takeoff.conductor_count<1 || takeoff.conductor_count>1000
          || !metric(takeoff.total_conductor_meters)
          || takeoff.one_conductor_meters!==takeoff.conduit_meters
          || Math.abs(takeoff.total_conductor_meters-takeoff.conduit_meters*takeoff.conductor_count)>1e-6)))
    || !Array.isArray(assignments) || !Array.isArray(reused) || reused.length !== assignments.length
    || reused.some((item, index) => !item || !assignments[index] || !Number.isSafeInteger(item.floor_id) || item.floor_id <= 0
      || !Number.isSafeInteger(item.route_id) || item.route_id <= 0 || assignmentKey(item) !== assignmentKey(assignments[index]))
    || !circuitAlgorithms.includes(result.algorithm) || result.optimality !== 'graph_heuristic_not_global_optimum'
    || (missing && configuration.routing_mode !== 'missing_devices')
    || !lengths(result) || !Array.isArray(result.segments) || (!missing && !result.segments.length)
    || result.segments.some((segment) => !point(segment.start) || !point(segment.end)
      || !['ceiling_service', 'wall_rise', 'wall_drop', 'riser', 'underground', 'underground_rise', 'underground_drop'].includes(segment.kind)
      || (segment.kind.startsWith('underground') && result.installation_method !== 'underground')
      || !metric(segment.horizontal_meters) || !metric(segment.vertical_meters))
    || !Array.isArray(result.branches) || covered.length !== expected.size || new Set(covered).size !== expected.size
    || covered.some((identity) => !expected.has(identity))
    || (!missing && issues.length > 0)
    || issues.some((issue) => !Number.isSafeInteger(issue.floor_id) || typeof issue.symbol_id !== 'string'
      || typeof issue.reason !== 'string' || !/^[A-Z_]+$/.test(issue.reason))
    || result.branches.some((branch) => !expected.has(`${branch.floor_id}:${branch.symbol_id}`) || !lengths(branch)
      || !Array.isArray(branch.points) || !branch.points.length || branch.points.some((p) => !point(p))
      || (branch.observed_attachment != null && (!Number.isSafeInteger(branch.observed_attachment.segment_index)
        || branch.observed_attachment.segment_index < 0 || !point(branch.observed_attachment.anchor)
        || !assignments.some(item => assignmentKey(item) === assignmentKey(branch.observed_attachment))
        || ['floor_id', 'x', 'y', 'elevation_meters'].some(key => branch.observed_attachment.anchor[key] !== branch.points[0][key])))
      || !Array.isArray(branch.segment_indices) || branch.segment_indices.some((index) => !Number.isSafeInteger(index)
        || index < 0 || index >= result.segments.length))) {
    throw new Error('Invalid circuit preview response.')
  }
}
