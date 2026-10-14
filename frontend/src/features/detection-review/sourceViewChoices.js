export function sourceViewChoices(record) {
  if (!record?.candidate?.payload?.warnings?.some(w => w.code === 'separate_source_views')) return []
  try {
    const parameter = record.candidate.provenance.inference_parameters.find(p => p.name === 'source-view-regions')
    const rows = JSON.parse(parameter?.value || '[]')
    const plane = record.candidate.payload.source_plane
    if (!Array.isArray(rows) || rows.length < 2 || rows.length > 8) return []
    if (!rows.every(row => typeof row.label === 'string' && row.label.length <= 255
      && row.region && ['x', 'y', 'width', 'height'].every(k => Number.isInteger(row.region[k]))
      && row.region.x >= 0 && row.region.y >= 0 && row.region.width > 0 && row.region.height > 0
      && row.region.x + row.region.width <= plane.width_pixels
      && row.region.y + row.region.height <= plane.height_pixels)) return []
    return [...rows].sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }))
  } catch { return [] }
}
