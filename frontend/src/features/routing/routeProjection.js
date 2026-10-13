import { WIRING_COLORS } from './wiringDesign.js'

export function routeWorldPositions(segment) {
  return [segment.start.x, segment.start.elevation_meters, segment.start.y,
    segment.end.x, segment.end.elevation_meters, segment.end.y]
}

// Display policy only: never infer installation methods from a glyph or height.
export function routeAppearance(kind) {
  if (kind === 'device_connector') return { color: WIRING_COLORS.wall, label: 'Device attachment · display only', dashed: false }
  if (kind === 'ceiling_service') return { color: WIRING_COLORS.ceiling, label: 'Generated ceiling/service run', dashed: false }
  if (kind === 'wall_rise' || kind === 'wall_drop') return { color: WIRING_COLORS.wall, label: 'Generated wall rise/drop', dashed: true }
  if (kind === 'riser') return { color: WIRING_COLORS.riser, label: 'Generated inter-floor riser', dashed: false }
  if (kind === 'underground') return { color: WIRING_COLORS.underground, label: 'Generated underground run', dashed: true }
  if (kind === 'underground_rise' || kind === 'underground_drop') return { color: WIRING_COLORS.underground, label: 'Generated floor passage', dashed: true }
  return { color: WIRING_COLORS.unresolved, label: 'Stored wiring — installation unresolved', dashed: true }
}

export function projectRoute(record, layout) {
  if (!record || record.stale || record.layout_versions[String(layout.project_floor_id)] !== layout.id) return []
  const config = record.configuration.floors.find((f) => f.floor_id === layout.project_floor_id)
  if (!config) return []
  return record.result.segments.filter((s) => s.start.floor_id === config.floor_id || s.end.floor_id === config.floor_id)
    .map((s) => ({ ...s, start: { ...s.start, x: s.start.x - config.offset_x, y: s.start.y - config.offset_y },
      end: { ...s.end, x: s.end.x - config.offset_x, y: s.end.y - config.offset_y } }))
}
