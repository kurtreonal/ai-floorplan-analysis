// Presentation only: never infer or approve an electrical class from a mesh.
export function deviceFamily(name = '') {
  const text = String(name).toLowerCase()
  if (/home.?run|circuit.*notation/.test(text)) return 'annotation'
  if (/troffer/.test(text)) return 'troffer'
  if (/fluorescent|linear|strip light/.test(text)) return 'linear-light'
  if (/downlight|light point|lighting point|recessed|pendant|ceiling light/.test(text)) return 'round-light'
  if (/panelboard|panel board|distribution board|electrical panel/.test(text)) return 'panel'
  if (/pull station|manual.*call point/.test(text)) return 'pull-station'
  if (/smoke|heat detector/.test(text)) return 'detector'
  if (/alarm|bell|horn|sounder/.test(text)) return 'alarm'
  if (/outlet|receptacle|socket|data port|connection port/.test(text)) return 'outlet'
  if (/switch/.test(text)) return 'switch'
  return 'unknown'
}

export function describeReviewSymbol(symbol, record, legends = []) {
  const legend = legends.find((item) => item.id === symbol.symbol_legend_id)
  const saved = record.review?.symbols.find((item) => item.id === symbol.id)
  const candidate = record.candidate.payload.symbols.items.find((item) => item.id === symbol.id)
  // A persisted class may be inactive now: retain its name, not a new approval.
  const savedName = symbol.symbol_legend_id && saved?.symbol_legend_id === symbol.symbol_legend_id
    ? saved.class_name : null
  const mappedName = legend?.name || savedName
  const name = mappedName || candidate?.observed_label || 'Unclassified device'
  return {
    name, family: deviceFamily(name), mapped: Boolean(mappedName),
    label: mappedName ? name : `${name} · proposal`,
    originalLabel: candidate?.observed_label || 'Unclassified device',
  }
}

export function clampDevicePoint(point, width, height) {
  if (![point.x, point.y].every(Number.isFinite)) return null
  return { x: Math.round(Math.max(0, Math.min(width, point.x))), y: Math.round(Math.max(0, Math.min(height, point.y))) }
}

// Keep display-only names, mesh metadata and estimated widths out of strict API writes.
export function reviewGeometryPayload(draft) {
  return {
    walls: draft.walls.map(({ id, disposition, start, end }) => ({ id, disposition, start, end })),
    rooms: draft.rooms.map(({ id, disposition, name, boundary }) => ({ id, disposition, name, boundary })),
    symbols: draft.symbols.map(({ id, disposition, center, symbol_legend_id }) => ({ id, disposition, center, symbol_legend_id })),
  }
}
