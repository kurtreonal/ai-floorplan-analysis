// Match the existing backend Obstacle contract; no position or height defaults.
export const MAX_ROUTE_OBSTACLES = 128
export const OBSTACLE_FIELDS = ['min_x', 'min_y', 'max_x', 'max_y', 'bottom', 'top']

function objectWithKeys(value, keys) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key))
}

function ordered(value) {
  if (value.min_x >= value.max_x || value.min_y >= value.max_y || value.bottom >= value.top) {
    throw new Error('Minimum x, y and elevation must each be less than the corresponding maximum.')
  }
}

export function normalizeRouteObstacles(raw, floorId) {
  if (!Number.isSafeInteger(floorId) || floorId <= 0) throw new Error('An existing floor is required for obstacles.')
  const values = raw === undefined ? [] : raw
  if (!Array.isArray(values) || values.length > MAX_ROUTE_OBSTACLES) {
    throw new Error(`Use at most ${MAX_ROUTE_OBSTACLES} explicit rectangular obstacles.`)
  }
  return values.map((value) => {
    if (!objectWithKeys(value, ['floor_id', ...OBSTACLE_FIELDS]) || value.floor_id !== floorId
      || !OBSTACLE_FIELDS.every((key) => Number.isFinite(value[key]))) {
      throw new Error('Obstacle bounds must be finite numbers on this floor, with no unsupported fields.')
    }
    ordered(value)
    return { floor_id: floorId, ...Object.fromEntries(OBSTACLE_FIELDS.map((key) => [key, value[key]])) }
  })
}

export function obstacleRows(raw, floorId) {
  return normalizeRouteObstacles(raw, floorId).map((value, index) => ({
    row_id: index + 1, ...Object.fromEntries(OBSTACLE_FIELDS.map((key) => [key, String(value[key])])),
  }))
}

function rowValue(row) {
  if (!objectWithKeys(row, ['row_id', ...OBSTACLE_FIELDS])
    || !Number.isSafeInteger(row.row_id) || row.row_id <= 0) {
    throw new Error('The obstacle row contains malformed or unsupported fields.')
  }
  const values = {}
  for (const key of OBSTACLE_FIELDS) {
    const text = row[key]
    if (typeof text !== 'string' || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(text.trim())
      || !Number.isFinite(Number(text))) {
      throw new Error('Enter finite numbers for all six obstacle bounds.')
    }
    values[key] = Number(text)
  }
  ordered(values)
  return values
}

export function routeObstacleRowError(row) {
  try { rowValue(row); return '' } catch (error) { return error.message }
}

export function routingObstaclesFromRows(rows, floorId) {
  if (!Array.isArray(rows) || rows.length > MAX_ROUTE_OBSTACLES) {
    throw new Error(`Use at most ${MAX_ROUTE_OBSTACLES} explicit rectangular obstacles.`)
  }
  if (new Set(rows.map((row) => row?.row_id)).size !== rows.length) {
    throw new Error('Obstacle rows must have distinct identities.')
  }
  return normalizeRouteObstacles(rows.map((row, index) => {
    try { return { floor_id: floorId, ...rowValue(row) } }
    catch (error) { throw new Error(`Obstacle ${index + 1}: ${error.message}`, { cause: error }) }
  }), floorId)
}
