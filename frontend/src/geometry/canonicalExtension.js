const EXTENSION_SCHEMA_VERSION = 2
const BASE_SCHEMA_VERSION = 1
const MAX_IMAGE_EDGE = 10000
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

function point(value, coordinateSystem = null) {
  const data = exactObject(value, ['x', 'y'])
  const x = finiteNumber(data.x, { nonnegative: true })
  const y = finiteNumber(data.y, { nonnegative: true })
  if (coordinateSystem && (x > coordinateSystem.width_meters || y > coordinateSystem.height_meters)) fail()
  return { x: roundMetric(x), y: roundMetric(y) }
}

function sourcePlaneReference(value) {
  const data = exactObject(value, ['floor_plan_page_id', 'source_artifact_id', 'width_pixels', 'height_pixels'])
  const pageId = identifier(data.floor_plan_page_id)
  const artifactId = identifier(data.source_artifact_id)
  const width = integer(data.width_pixels)
  const height = integer(data.height_pixels)
  if (width <= 0 || height <= 0 || width > MAX_IMAGE_EDGE || height > MAX_IMAGE_EDGE) fail()
  return {
    floor_plan_page_id: pageId,
    source_artifact_id: artifactId,
    width_pixels: width,
    height_pixels: height,
  }
}

function opening(value, cs, validWallIds) {
  const data = exactObject(value, ['id', 'source_candidate_id', 'opening_type', 'start', 'end', 'associated_wall_id'])
  const openingId = identifier(data.id)
  const candidateId = data.source_candidate_id === null ? null : name(data.source_candidate_id, { maximum: 128 })
  if (!['door', 'window', 'opening', 'unknown'].includes(data.opening_type)) fail()
  const startPt = point(data.start, cs)
  const endPt = point(data.end, cs)
  if (close(startPt.x, endPt.x) && close(startPt.y, endPt.y)) fail()
  let associatedWallId = null
  if (data.associated_wall_id !== null) {
    associatedWallId = identifier(data.associated_wall_id)
    if (validWallIds && !validWallIds.has(associatedWallId)) fail()
  }
  return {
    id: openingId,
    source_candidate_id: candidateId,
    opening_type: data.opening_type,
    start: startPt,
    end: endPt,
    associated_wall_id: associatedWallId,
  }
}

function panel(value, cs) {
  const data = exactObject(value, ['id', 'source_candidate_id', 'name', 'position', 'orientation_degrees', 'bounds'])
  const panelId = identifier(data.id)
  const candidateId = data.source_candidate_id === null ? null : name(data.source_candidate_id, { maximum: 128 })
  const panelName = name(data.name, { nullable: true })
  const pos = point(data.position, cs)
  let orientation = null
  if (data.orientation_degrees !== null) {
    orientation = finiteNumber(data.orientation_degrees, { nonnegative: true })
    if (orientation >= 360) fail()
    orientation = roundMetric(orientation)
  }
  let bounds = null
  if (data.bounds !== null) {
    const bData = exactObject(data.bounds, ['width_meters', 'height_meters'])
    const w = roundMetric(finiteNumber(bData.width_meters, { positive: true }))
    const h = roundMetric(finiteNumber(bData.height_meters, { positive: true }))
    bounds = { width_meters: w, height_meters: h }
  }
  return {
    id: panelId,
    source_candidate_id: candidateId,
    name: panelName,
    position: pos,
    orientation_degrees: orientation,
    bounds,
  }
}

function symbolDetail(value, validSymbolIds) {
  const data = exactObject(value, ['symbol_id', 'orientation_degrees', 'bounds', 'provenance'])
  const symbolId = name(data.symbol_id, { maximum: 128 })
  if (validSymbolIds && !validSymbolIds.has(symbolId)) fail()
  let orientation = null
  if (data.orientation_degrees !== null) {
    orientation = finiteNumber(data.orientation_degrees, { nonnegative: true })
    if (orientation >= 360) fail()
    orientation = roundMetric(orientation)
  }
  let bounds = null
  if (data.bounds !== null) {
    const bData = exactObject(data.bounds, ['width_meters', 'height_meters'])
    const w = roundMetric(finiteNumber(bData.width_meters, { positive: true }))
    const h = roundMetric(finiteNumber(bData.height_meters, { positive: true }))
    bounds = { width_meters: w, height_meters: h }
  }
  const provenance = name(data.provenance, { nullable: true, maximum: 255 })
  return {
    symbol_id: symbolId,
    orientation_degrees: orientation,
    bounds,
    provenance,
  }
}

function routeDetail(value, validRouteIds) {
  const data = exactObject(value, ['route_id', 'route_kind', 'provenance_ref'])
  const routeId = identifier(data.route_id)
  if (validRouteIds && !validRouteIds.has(routeId)) fail()
  if (!['observed', 'generated'].includes(data.route_kind)) fail()
  const provenanceRef = name(data.provenance_ref, { nullable: true, maximum: 255 })
  return {
    route_id: routeId,
    route_kind: data.route_kind,
    provenance_ref: provenanceRef,
  }
}

function deepFreeze(value) {
  Object.values(value).forEach((item) => {
    if (item && typeof item === 'object' && !Object.isFrozen(item)) deepFreeze(item)
  })
  return Object.freeze(value)
}

export function normalizeCanonicalExtension(value, baseGeometry = null) {
  const data = exactObject(value, [
    'extension_schema_version',
    'base_schema_version',
    'source_plane_reference',
    'openings',
    'panels',
    'symbol_details',
    'route_details',
  ])
  if (data.extension_schema_version !== EXTENSION_SCHEMA_VERSION || !Number.isSafeInteger(data.extension_schema_version)) {
    fail()
  }
  if (data.base_schema_version !== BASE_SCHEMA_VERSION || !Number.isSafeInteger(data.base_schema_version)) {
    fail()
  }

  const sourcePlane = sourcePlaneReference(data.source_plane_reference)
  let cs = null
  let validWallIds = null
  let validSymbolIds = null
  let validRouteIds = null

  if (baseGeometry) {
    cs = baseGeometry.coordinate_system
    if (
      sourcePlane.width_pixels !== cs.image_width_pixels
      || sourcePlane.height_pixels !== cs.image_height_pixels
    ) {
      fail()
    }
    validWallIds = new Set(baseGeometry.walls.map((w) => w.id))
    validSymbolIds = new Set(baseGeometry.symbols.map((s) => s.id))
    validRouteIds = new Set(baseGeometry.routes.map((r) => r.id))
  }

  if (!Array.isArray(data.openings) || !Array.isArray(data.panels) || !Array.isArray(data.symbol_details) || !Array.isArray(data.route_details)) {
    fail()
  }

  const normalizedOpenings = data.openings.map((item) => opening(item, cs, validWallIds))
  const openingIds = new Set(normalizedOpenings.map((o) => o.id))
  if (openingIds.size !== normalizedOpenings.length) fail()

  const normalizedPanels = data.panels.map((item) => panel(item, cs))
  const panelIds = new Set(normalizedPanels.map((p) => p.id))
  if (panelIds.size !== normalizedPanels.length) fail()

  const normalizedSymbolDetails = data.symbol_details.map((item) => symbolDetail(item, validSymbolIds))
  const symbolDetailIds = new Set(normalizedSymbolDetails.map((s) => s.symbol_id))
  if (symbolDetailIds.size !== normalizedSymbolDetails.length) fail()

  const normalizedRouteDetails = data.route_details.map((item) => routeDetail(item, validRouteIds))
  const routeDetailIds = new Set(normalizedRouteDetails.map((r) => r.route_id))
  if (routeDetailIds.size !== normalizedRouteDetails.length) fail()

  return deepFreeze({
    extension_schema_version: EXTENSION_SCHEMA_VERSION,
    base_schema_version: BASE_SCHEMA_VERSION,
    source_plane_reference: sourcePlane,
    openings: normalizedOpenings,
    panels: normalizedPanels,
    symbol_details: normalizedSymbolDetails,
    route_details: normalizedRouteDetails,
  })
}

export function composeCanonicalView(baseGeometry, extension = null) {
  return {
    ...baseGeometry,
    extension: extension ? normalizeCanonicalExtension(extension, baseGeometry) : null,
  }
}

export function preserveExtensionOnSymbolMove(extension, symbolId, newPosition) {
  if (!extension) return null
  if (!symbolId || !newPosition) return extension
  // Symbol detail orientations and bounds are preserved; position is tracked in base v1
  return extension
}
