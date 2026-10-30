export function groupBOMRows(rows = []) {
  const groups = new Map()
  for (const row of rows) {
    const key = row.kind === 'device' ? `device:${row.item_key || [row.floor_id,row.floor_plan_id,row.class_id,...(row.symbol_ids || [])].join(':')}`
      : `path:${JSON.stringify([row.floor_id,row.floor_plan_id,row.page_id,row.candidate_run_id,row.saved_route_version_id,row.path_ids || [row.path_id]])}`
    if (!groups.has(key)) groups.set(key,{key,kind:row.kind,layout_category:row.layout_category,name:row.kind === 'device' ? row.name : `Wiring path ${row.path_id || `route ${row.saved_route_version_id}`}`,components:[]})
    groups.get(key).components.push(row)
  }
  return [...groups.values()]
}

export function compatibleQuote(row, entries) {
  const matches = entries.filter(q=>!q.excluded && (row.compatible_prices ? row.compatible_prices.includes(q.row_id) : q.material_id === row.material_id))
  return matches.length === 1 ? matches[0].row_id : ''
}
