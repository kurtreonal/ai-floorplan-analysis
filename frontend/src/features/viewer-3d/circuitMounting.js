// Version-bound planning inputs, not approval or a second geometry model.
export function bindCircuitMounting(scene, record, layout) {
  if (!record || record.stale || record.project_id !== layout.project_id
    || record.layout_versions?.[String(layout.project_floor_id)] !== layout.id
    || !['preview_not_saved', 'saved_planning'].includes(record.result?.status)
    || record.result.algorithm !== 'greedy_shared_service_tree_v1') return scene
  const targets = record.configuration?.targets
  if (!Array.isArray(targets)) return scene
  const positions = new Map(layout.geometry.symbols.map((symbol) => [symbol.id, symbol.position]))
  const walls = new Set(scene.walls.map((wall) => wall.id))
  const inputs = new Map(targets.filter((target) => {
    const source = positions.get(target.symbol_id)
    return target.floor_id === layout.project_floor_id && source && source.x === target.x && source.y === target.y
      && Number.isFinite(target.elevation_meters) && (target.wall_id == null || walls.has(target.wall_id))
  }).map((target) => [target.symbol_id, target]))
  return { ...scene, symbols: scene.symbols.map((symbol) => {
    const input = inputs.get(symbol.id)
    return input ? { ...symbol, installation: {
      elevation_meters: input.elevation_meters, wall_id: input.wall_id ?? null,
      provenance: 'designer_supplied_planning', state: record.result.status,
      route_version_id: record.id ?? null,
    } } : symbol
  }) }
}
