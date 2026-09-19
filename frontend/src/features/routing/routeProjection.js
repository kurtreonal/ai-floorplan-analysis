export function routeWorldPositions(segment) {
  return [segment.start.x, segment.start.elevation_meters, segment.start.y,
    segment.end.x, segment.end.elevation_meters, segment.end.y]
}

export function projectRoute(record, layout) {
  if (!record || record.stale || record.layout_versions[String(layout.project_floor_id)] !== layout.id) return []
  const config = record.configuration.floors.find((f) => f.floor_id === layout.project_floor_id)
  if (!config) return []
  return record.result.segments.filter((s) => s.start.floor_id === config.floor_id || s.end.floor_id === config.floor_id)
    .map((s) => ({ ...s, start: { ...s.start, x: s.start.x - config.offset_x, y: s.start.y - config.offset_y },
      end: { ...s.end, x: s.end.x - config.offset_x, y: s.end.y - config.offset_y } }))
}
