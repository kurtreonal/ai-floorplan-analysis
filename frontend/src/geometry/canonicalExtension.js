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

function symbolDetail(value, validSymbolIds, version = 2, validWallIds = null) {
  const hasInstallation = version >= 3 && value !== null && typeof value === 'object' && Object.hasOwn(value, 'installation')
  const data = exactObject(value, ['symbol_id', 'orientation_degrees', 'bounds', 'provenance', ...(hasInstallation ? ['installation'] : [])])
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
  let installation
  if (hasInstallation) {
    const mount = exactObject(data.installation, ['elevation_meters', 'wall_id'])
    const level = finiteNumber(mount.elevation_meters)
    const wallId = mount.wall_id === null ? null : identifier(mount.wall_id)
    if (wallId !== null && validWallIds && !validWallIds.has(wallId)) fail()
    installation = {elevation_meters: level, wall_id: wallId}
  }
  return {
    symbol_id: symbolId,
    orientation_degrees: orientation,
    bounds,
    provenance,
    ...(installation ? {installation} : {}),
  }
}

function routeDetail(value, validRouteIds, version=2, baseGeometry=null) {
  const data = exactObject(value, ['route_id', 'route_kind', 'provenance_ref',...(version>=4 ? ['device_connections'] : []),
    ...(version>=5 ? ['junction_connections','circuit_id'] : [])])
  const routeId = identifier(data.route_id)
  if (validRouteIds && !validRouteIds.has(routeId)) fail()
  if (!['observed', 'generated'].includes(data.route_kind)) fail()
  const provenanceRef = name(data.provenance_ref, { nullable: true, maximum: 255 })
  let connections
  if (version>=4) {
    if (!Array.isArray(data.device_connections) || data.device_connections.length>512) fail()
    const indices=new Set()
    connections=data.device_connections.map(raw => {
      const contact=exactObject(raw,['symbol_id','point_index','anchor'])
      const symbolId=name(contact.symbol_id,{maximum:128}), index=integer(contact.point_index)
      if (index<0 || index>2047 || indices.has(index)) fail()
      indices.add(index)
      const anchor=exactObject(contact.anchor,['x','y','elevation_meters'])
      const normalized={...point({x:anchor.x,y:anchor.y},baseGeometry?.coordinate_system),elevation_meters:finiteNumber(anchor.elevation_meters)}
      if (baseGeometry) {
        const symbol=baseGeometry.symbols.find(s => s.id===symbolId), route=baseGeometry.routes.find(r => r.id===routeId)
        const p=route?.points[index]
        if (!symbol || !p || !close(p.x,normalized.x) || !close(p.y,normalized.y)
          || !close(symbol.position.x,normalized.x) || !close(symbol.position.y,normalized.y)) fail()
      }
      return {symbol_id:symbolId,point_index:index,anchor:normalized}
    })
  }
  let junctions, circuit
  if (version>=5) {
    circuit = name(data.circuit_id,{nullable:true,maximum:80})
    if (!Array.isArray(data.junction_connections) || data.junction_connections.length>512) fail()
    const indices=new Set(connections.map(c=>c.point_index))
    junctions=data.junction_connections.map(raw=>{
      const contact=exactObject(raw,['junction_id','point_index','anchor'])
      const identity=name(contact.junction_id,{maximum:64}), index=integer(contact.point_index)
      if (!/^junction-[0-9]{4}$/.test(identity) || index<0 || index>2047 || indices.has(index)) fail()
      indices.add(index)
      const anchor=exactObject(contact.anchor,['x','y','elevation_meters'])
      const normalized={...point({x:anchor.x,y:anchor.y},baseGeometry?.coordinate_system),elevation_meters:finiteNumber(anchor.elevation_meters)}
      if (baseGeometry) {
        const p=baseGeometry.routes.find(r=>r.id===routeId)?.points[index]
        if (!p || p.project_floor_id!==baseGeometry.floor.project_floor_id || Object.keys(normalized).some(k=>!close(p[k],normalized[k]))) fail()
      }
      return {junction_id:identity,point_index:index,anchor:normalized}
    })
  }
  return {
    route_id: routeId,
    route_kind: data.route_kind,
    provenance_ref: provenanceRef,
    ...(connections ? {device_connections:connections} : {}),
    ...(junctions ? {junction_connections:junctions,circuit_id:circuit} : {}),
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
  if (![2, 3, 4, 5].includes(data.extension_schema_version) || !Number.isSafeInteger(data.extension_schema_version)) {
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

  const normalizedSymbolDetails = data.symbol_details.map((item) => symbolDetail(item, validSymbolIds, data.extension_schema_version, validWallIds))
  const symbolDetailIds = new Set(normalizedSymbolDetails.map((s) => s.symbol_id))
  if (symbolDetailIds.size !== normalizedSymbolDetails.length) fail()

  const normalizedRouteDetails = data.route_details.map((item) => routeDetail(item, validRouteIds,data.extension_schema_version,baseGeometry))
  const routeDetailIds = new Set(normalizedRouteDetails.map((r) => r.route_id))
  if (routeDetailIds.size !== normalizedRouteDetails.length) fail()
  if (data.extension_schema_version>=4) {
    const mounts=new Map(normalizedSymbolDetails.filter(s => s.installation).map(s => [s.symbol_id,s.installation]))
    for (const route of normalizedRouteDetails) for (const connection of route.device_connections) {
      if (!mounts.has(connection.symbol_id) || !close(connection.anchor.elevation_meters,mounts.get(connection.symbol_id).elevation_meters)) fail()
    }
  }
  if (data.extension_schema_version>=5) {
    const junctions=new Map()
    for (const route of normalizedRouteDetails) for (const contact of route.junction_connections) {
      if (!junctions.has(contact.junction_id)) junctions.set(contact.junction_id,[])
      junctions.get(contact.junction_id).push({route,anchor:contact.anchor})
    }
    if (junctions.size>4096 || [...junctions.values()].reduce((sum,rows)=>sum+rows.length,0)>16384) fail()
    for (const contacts of junctions.values()) {
      if (new Set(contacts.map(c=>c.route.route_id)).size<2) fail()
      const first=contacts[0]
      if (contacts.some(c=>c.route.circuit_id!==first.route.circuit_id || Object.keys(first.anchor).some(k=>!close(c.anchor[k],first.anchor[k])))) fail()
    }
  }

  return deepFreeze({
    extension_schema_version: data.extension_schema_version,
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
