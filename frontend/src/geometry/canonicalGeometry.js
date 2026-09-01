const SCHEMA_VERSION = 1
const MAX_IMAGE_EDGE = 4096
const MAX_NAME_LENGTH = 255
const ERROR_MESSAGE = 'The canonical geometry document is invalid.'

function fail() {
  throw new TypeError(ERROR_MESSAGE)
}

function exactObject(value, keys) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) fail()
  const actual = Object.keys(value)
  if (actual.length !== keys.length || actual.some((key) => !keys.includes(key))) fail()
  return value
}

function finiteNumber(value, { positive = false, nonnegative = false } = {}) {
  if (typeof value !== 'number' || !Number.isFinite(value)) fail()
  if ((positive && value <= 0) || (nonnegative && value < 0)) fail()
  return value
}

function identifier(value) {
  if (!Number.isSafeInteger(value) || value <= 0) fail()
  return value
}

function integer(value) {
  if (!Number.isSafeInteger(value)) fail()
  return value
}

function name(value, { nullable = false, maximum = MAX_NAME_LENGTH } = {}) {
  if (nullable && value === null) return null
  if (typeof value !== 'string' || value.length === 0 || value.length > maximum || value !== value.trim() || value.includes('\0')) fail()
  return value
}

function roundMetric(value) {
  const canScaleSafely = Math.abs(value) <= Number.MAX_SAFE_INTEGER / 1e9
  const rounded = canScaleSafely ? Math.round(value * 1e9) / 1e9 : value
  return Object.is(rounded, -0) ? 0 : rounded
}

function close(left, right) {
  return Math.abs(left - right) <= 5e-9
}

function point(value, coordinateSystem) {
  const data = exactObject(value, ['x', 'y'])
  const x = finiteNumber(data.x, { nonnegative: true })
  const y = finiteNumber(data.y, { nonnegative: true })
  if (x > coordinateSystem.width_meters || y > coordinateSystem.height_meters) fail()
  return { x: roundMetric(x), y: roundMetric(y) }
}

function coordinateSystem(value) {
  const keys = ['unit', 'origin', 'x_direction', 'y_direction', 'pixels_per_meter', 'image_width_pixels', 'image_height_pixels', 'width_meters', 'height_meters']
  const data = exactObject(value, keys)
  if (data.unit !== 'meter' || data.origin !== 'image_top_left' || data.x_direction !== 'right' || data.y_direction !== 'down') fail()
  const pixelsPerMeter = finiteNumber(data.pixels_per_meter, { positive: true })
  const imageWidth = integer(data.image_width_pixels)
  const imageHeight = integer(data.image_height_pixels)
  if (imageWidth <= 0 || imageHeight <= 0 || imageWidth > MAX_IMAGE_EDGE || imageHeight > MAX_IMAGE_EDGE) fail()
  const width = finiteNumber(data.width_meters, { positive: true })
  const height = finiteNumber(data.height_meters, { positive: true })
  if (!close(width, imageWidth / pixelsPerMeter) || !close(height, imageHeight / pixelsPerMeter)) fail()
  return {
    unit: 'meter', origin: 'image_top_left', x_direction: 'right', y_direction: 'down',
    pixels_per_meter: pixelsPerMeter, image_width_pixels: imageWidth, image_height_pixels: imageHeight,
    width_meters: roundMetric(width), height_meters: roundMetric(height),
  }
}

function nullablePositive(value) {
  return value === null ? null : roundMetric(finiteNumber(value, { positive: true }))
}

function wall(value, cs) {
  const keys = ['id', 'source_candidate_id', 'processing_job_id', 'status', 'start', 'end', 'length_meters', 'angle_degrees', 'thickness_meters', 'height_meters']
  const data = exactObject(value, keys)
  const start = point(data.start, cs)
  const end = point(data.end, cs)
  const length = finiteNumber(data.length_meters, { nonnegative: true })
  const derived = Math.hypot(end.x - start.x, end.y - start.y)
  const angle = finiteNumber(data.angle_degrees)
  if (!close(length, derived) || angle < 0 || angle >= 180 || !['detected', 'verified'].includes(data.status)) fail()
  return {
    id: identifier(data.id),
    source_candidate_id: data.source_candidate_id === null ? null : identifier(data.source_candidate_id),
    processing_job_id: data.processing_job_id === null ? null : identifier(data.processing_job_id),
    status: data.status, start, end, length_meters: roundMetric(derived), angle_degrees: roundMetric(angle),
    thickness_meters: nullablePositive(data.thickness_meters), height_meters: nullablePositive(data.height_meters),
  }
}

function room(value, cs) {
  const data = exactObject(value, ['id', 'name', 'boundary'])
  if (!Array.isArray(data.boundary) || data.boundary.length < 3) fail()
  const boundary = data.boundary.map((item) => point(item, cs))
  if (boundary.some((item, index) => item.x === boundary[(index + 1) % boundary.length].x && item.y === boundary[(index + 1) % boundary.length].y)) fail()
  return { id: identifier(data.id), name: name(data.name, { nullable: true }), boundary }
}

function symbol(value, cs) {
  const data = exactObject(value, ['id', 'source_type', 'source_record_id', 'processing_job_id', 'status', 'class', 'position'])
  const sourceRecordId = identifier(data.source_record_id)
  const expectedStatus = { detected: 'confirmed', manual: 'manually_added' }[data.source_type]
  if (!expectedStatus || data.status !== expectedStatus || data.id !== `${data.source_type}:${sourceRecordId}`) fail()
  const classification = exactObject(data.class, ['id', 'name'])
  if (!Number.isSafeInteger(classification.id) || classification.id < 0) fail()
  return {
    id: data.id, source_type: data.source_type, source_record_id: sourceRecordId,
    processing_job_id: identifier(data.processing_job_id), status: data.status,
    class: { id: classification.id, name: name(classification.name) }, position: point(data.position, cs),
  }
}

function route(value, cs) {
  const data = exactObject(value, ['id', 'points'])
  if (!Array.isArray(data.points) || data.points.length < 2) fail()
  return {
    id: identifier(data.id),
    points: data.points.map((item) => {
      const routePoint = exactObject(item, ['project_floor_id', 'x', 'y', 'elevation_meters'])
      const metric = point({ x: routePoint.x, y: routePoint.y }, cs)
      return { project_floor_id: identifier(routePoint.project_floor_id), ...metric, elevation_meters: roundMetric(finiteNumber(routePoint.elevation_meters)) }
    }),
  }
}

function deepFreeze(value) {
  Object.values(value).forEach((item) => {
    if (item && typeof item === 'object' && !Object.isFrozen(item)) deepFreeze(item)
  })
  return Object.freeze(value)
}

export function normalizeCanonicalGeometry(value) {
  const keys = ['schema_version', 'project_id', 'floor', 'floor_plan_id', 'coordinate_system', 'walls', 'rooms', 'symbols', 'routes']
  const data = exactObject(value, keys)
  if (data.schema_version !== SCHEMA_VERSION || !Number.isSafeInteger(data.schema_version)) fail()
  const floorData = exactObject(data.floor, ['project_floor_id', 'name', 'sort_order', 'elevation_meters'])
  const cs = coordinateSystem(data.coordinate_system)
  for (const collection of ['walls', 'rooms', 'symbols', 'routes']) {
    if (!Array.isArray(data[collection])) fail()
  }
  return deepFreeze({
    schema_version: SCHEMA_VERSION,
    project_id: identifier(data.project_id),
    floor: {
      project_floor_id: identifier(floorData.project_floor_id), name: name(floorData.name, { maximum: 100 }),
      sort_order: integer(floorData.sort_order), elevation_meters: roundMetric(finiteNumber(floorData.elevation_meters)),
    },
    floor_plan_id: identifier(data.floor_plan_id), coordinate_system: cs,
    walls: data.walls.map((item) => wall(item, cs)), rooms: data.rooms.map((item) => room(item, cs)),
    symbols: data.symbols.map((item) => symbol(item, cs)), routes: data.routes.map((item) => route(item, cs)),
  })
}

function canonicalSymbolId(value) {
  if (typeof value !== 'string' || !/^(detected|manual):[1-9]\d*$/.test(value)) fail()
  const sourceRecordId = Number(value.slice(value.indexOf(':') + 1))
  if (!Number.isSafeInteger(sourceRecordId)) fail()
  return value
}

export function moveCanonicalSymbol(value, symbolId, newCanonicalPosition) {
  const geometry = normalizeCanonicalGeometry(value)
  const normalizedSymbolId = canonicalSymbolId(symbolId)
  const proposedPosition = exactObject(newCanonicalPosition, ['x', 'y'])
  const x = finiteNumber(proposedPosition.x, { nonnegative: true })
  const y = finiteNumber(proposedPosition.y, { nonnegative: true })
  if (x > geometry.coordinate_system.width_meters
    || y > geometry.coordinate_system.height_meters) fail()

  const matchingIndexes = geometry.symbols.flatMap(
    (item, index) => item.id === normalizedSymbolId ? [index] : [],
  )
  if (matchingIndexes.length !== 1) fail()

  const normalizedPosition = { x: roundMetric(x), y: roundMetric(y) }
  const selectedIndex = matchingIndexes[0]
  const selected = geometry.symbols[selectedIndex]
  if (selected.position.x === normalizedPosition.x
    && selected.position.y === normalizedPosition.y) return geometry

  return normalizeCanonicalGeometry({
    ...geometry,
    symbols: geometry.symbols.map((item, index) => index === selectedIndex
      ? { ...item, position: normalizedPosition }
      : item),
  })
}

export function canonicalGeometriesEqual(left, right) {
  try {
    return JSON.stringify(normalizeCanonicalGeometry(left))
      === JSON.stringify(normalizeCanonicalGeometry(right))
  } catch {
    return false
  }
}
