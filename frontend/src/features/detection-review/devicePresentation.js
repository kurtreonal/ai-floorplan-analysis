import { legendDescription } from '../../api/legendChoices.js'

// Presentation only: never infer or approve an electrical class from a mesh.
export function deviceFamily(name = '') {
  const text = String(name).toLowerCase()
  if (/home.?run|circuit.*notation/.test(text)) return 'annotation'
  if (/troffer/.test(text)) return 'troffer'
  if (/fluorescent|linear|strip light/.test(text)) return 'linear-light'
  if (/downlight|light point|lighting point|recessed|pendant|ceiling light/.test(text)) return 'round-light'
  if (/led|floodlight|spotlight|luminaire|lighting fixture/.test(text)) return 'round-light'
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
  const trainingLegend = record.candidate.provenance?.model_release_id === 'development_multiclass56_yolo'
    ? candidate?.training_legend : null
  const trainedCatalogName = trainingLegend ? `${trainingLegend.name} [${trainingLegend.legend_entry}]` : null
  // Never equate checkpoint indices with database IDs, or merge equal wording
  // from different drawings. Exact linking does not approve the detection.
  const matches = legends.filter(item => item.is_active !== false && (candidate?.catalog_class_id != null
    ? item.class_id === candidate.catalog_class_id : trainedCatalogName && item.name === trainedCatalogName))
  const gangProposal=candidate?.gang_count_proposal
  const gangMatches=gangProposal ? legends.filter(item=>item.is_active!==false &&
    new RegExp(`\\b(${['','one','two','three'][gangProposal.count]}|${gangProposal.count})[ -]*gang\\b`,'i').test(legendDescription(item.name)) &&
    /device switch|gang switch/i.test(item.name) && (!trainingLegend || item.name.includes(`[${trainingLegend.legend_entry}]`) || gangProposal.basis==='user_requested_default')) : []
  const referenceMatches = legends.filter(item => item.is_active !== false && candidate?.observed_label &&
    legendDescription(item.name).trim().replace(/\s+/g,' ').toLowerCase() === legendDescription(candidate.observed_label).trim().replace(/\s+/g,' ').toLowerCase())
  const suggestedLegendId = gangProposal && gangProposal.basis!=='model_prediction'
    ? gangMatches.length===1 ? gangMatches[0].id : null : matches.length === 1 ? matches[0].id : referenceMatches.length === 1 ? referenceMatches[0].id : null
  // A persisted class may be inactive now: retain its name, not a new approval.
  const savedName = symbol.symbol_legend_id && saved?.symbol_legend_id === symbol.symbol_legend_id
    ? saved.class_name : null
  const mappedName = legend?.name || savedName
  const provisionalName=gangProposal?.basis==='user_requested_default' ? 'One gang switch (provisional)' : null
  const name = legendDescription(mappedName || provisionalName || trainingLegend?.name || (referenceMatches.length===1?referenceMatches[0].name:null) || candidate?.observed_label || 'Unclassified device')
  return {
    name, family: deviceFamily(name), mapped: Boolean(mappedName),
    legendId: legend?.id || symbol.symbol_legend_id || suggestedLegendId || null,
    label: name,
    originalLabel: candidate?.observed_label || 'Unclassified device',
    ...(gangProposal ? {gangProposal} : {}),
    // Display evidence follows a moved anchor; never send detector bounds in a review save.
    ...(candidate?.bounds && candidate.center ? { sourceBounds: {
      ...candidate.bounds,
      x: candidate.bounds.x + symbol.center.x - candidate.center.x,
      y: candidate.bounds.y + symbol.center.y - candidate.center.y,
    } } : {}),
    ...(trainingLegend || candidate?.catalog_class_id != null || gangProposal || suggestedLegendId ? {suggestedLegendId} : {}),
    ...(trainingLegend ? { trainingLegend } : {}),
  }
}

export function autoLinkSymbols(symbols, record, legends) {
  return symbols.map(symbol => {
    if (symbol.symbol_legend_id || symbol.disposition === 'rejected') return symbol
    const id = describeReviewSymbol(symbol,record,legends).suggestedLegendId
    const legend = legends.find(item => item.id === id)
    return legend && !/raceway conduit/i.test(legend.name) ? {...symbol,symbol_legend_id:id} : symbol
  })
}

export function relatedSymbolIds(symbols, selectedId, record) {
  const predictions = new Map(record.candidate.payload.symbols.items.map(item => [item.id,item]))
  function identity(symbol) {
    if (symbol.symbol_legend_id) return `catalog:${symbol.symbol_legend_id}`
    const candidate = predictions.get(symbol.id)
    if (candidate?.catalog_class_id != null) return `class:${candidate.catalog_class_id}`
    const training = record.candidate.provenance?.model_release_id === 'development_multiclass56_yolo' ? candidate?.training_legend : null
    return training ? JSON.stringify([training.legend_entry,training.name]) : `single:${symbol.id}`
  }
  const selected = symbols.find(symbol => symbol.id === selectedId)
  if (!selected || selected.disposition === 'rejected') return []
  const key = identity(selected)
  return symbols.filter(symbol => symbol.disposition !== 'rejected' && identity(symbol) === key).map(symbol => symbol.id)
}

export function updateRelatedSymbols(symbols, selectedId, record, patch) {
  const ids = new Set(relatedSymbolIds(symbols,selectedId,record))
  // Never copy positions, deletion state or detector evidence across devices.
  const changes = Object.fromEntries(['symbol_legend_id','custom_unit_price','gang_count_confirmed'].filter(key => Object.hasOwn(patch,key)).map(key => [key,patch[key]]))
  return symbols.map(symbol => ids.has(symbol.id) ? {...symbol,...changes,
    ...(Object.hasOwn(changes,'symbol_legend_id') && (changes.symbol_legend_id !== symbol.symbol_legend_id || changes.gang_count_confirmed) ? {disposition: symbol.disposition === 'added' ? 'added' : 'corrected'} : {})} : symbol)
}

export function clampDevicePoint(point, width, height) {
  if (![point.x, point.y].every(Number.isFinite)) return null
  return { x: Number(Math.max(0, Math.min(width, point.x)).toFixed(4)), y: Number(Math.max(0, Math.min(height, point.y)).toFixed(4)) }
}

// Keep display-only names, mesh metadata and estimated widths out of strict API writes.
export function reviewGeometryPayload(draft) {
  return {
    walls: draft.walls.map(({ id, disposition, start, end,estimated_thickness_pixels,thickness_meters,height_meters }) => ({ id, disposition, start, end,
      ...(Number.isFinite(estimated_thickness_pixels)?{estimated_thickness_pixels}:{} ),
      ...(Number.isFinite(thickness_meters)?{thickness_meters}:{}),...(Number.isFinite(height_meters)?{height_meters}:{}) })),
    rooms: draft.rooms.map(({ id, disposition, name, boundary }) => ({ id, disposition, name, boundary })),
    symbols: draft.symbols.map(({ id, disposition, center, symbol_legend_id, custom_unit_price, mounting_height_meters, mounting_wall_id, gang_count_confirmed,mounting_reference,mounting_height_source,terminal_offset_meters }) => ({ id, disposition, center, symbol_legend_id,
      ...Object.fromEntries(Object.entries({mounting_reference,mounting_height_source,terminal_offset_meters}).filter(([,v])=>v!=null)),
      ...(gang_count_confirmed ? {gang_count_confirmed:true} : {}),
      ...(mounting_height_meters != null ? {mounting_height_meters} : {}),
      ...(mounting_wall_id != null ? {mounting_wall_id} : {}),
      ...(custom_unit_price != null ? {custom_unit_price} : {}) })),
  }
}
