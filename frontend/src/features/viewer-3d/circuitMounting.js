// Version-bound planning inputs, not approval or a second geometry model.
export function bindCircuitMounting(scene, record, layout) {
  if (!record || record.stale || record.project_id !== layout.project_id
    || record.layout_versions?.[String(layout.project_floor_id)] !== layout.id
    || !record.result) return scene
  const circuit = ['preview_not_saved', 'saved_planning'].includes(record.result.status)
    && ['greedy_shared_service_tree_v1', 'assigned_missing_device_astar_v1'].includes(record.result.algorithm)
  const singleRoute = record.result.algorithm == null && record.id != null
    && record.configuration?.purpose === 'planning' && Array.isArray(record.result.segments)
  if (!circuit && !singleRoute) return scene
  let targets = circuit ? record.configuration?.targets : [record.configuration?.target].filter(Boolean)
  if (!Array.isArray(targets)) return scene
  if (record.result.algorithm === 'assigned_missing_device_astar_v1') {
    const routed = new Set(record.result.branches.map((branch) => `${branch.floor_id}:${branch.symbol_id}`))
    targets = targets.filter((target) => routed.has(`${target.floor_id}:${target.symbol_id}`))
  }
  const positions = new Map(layout.geometry.symbols.map((symbol) => [symbol.id, symbol.position]))
  const walls = new Set(scene.walls.map((wall) => wall.id))
  const endpoints = [...targets,record.configuration?.panel].filter(target => target?.symbol_id)
  const inputs = new Map(endpoints.filter((target) => {
    const source = positions.get(target.symbol_id)
    return target.floor_id === layout.project_floor_id && source && source.x === target.x && source.y === target.y
      && Number.isFinite(target.elevation_meters) && (target.wall_id == null || walls.has(target.wall_id))
  }).map((target) => [target.symbol_id, target]))
  return { ...scene, symbols: scene.symbols.map((symbol) => {
    const input = inputs.get(symbol.id)
    return input ? { ...symbol, installation: {
      elevation_meters: input.elevation_meters, wall_id: input.wall_id ?? null,
      floor_id: input.floor_id,
      provenance: 'designer_supplied_planning', state: record.result.status ?? 'saved_planning',
      route_version_id: record.id ?? null,
    } } : symbol
  }) }
}
