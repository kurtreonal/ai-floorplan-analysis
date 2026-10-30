// Observations stay in source pixels; they are not generated circuits or heights.
export function initialWiringDraft(record) {
  const saved = structuredClone(record.observed_wiring ?? record.review?.observed_wiring ?? [])
  const identities = new Set(saved.map((wire) => wire.id))
  const missing = (record.candidate?.payload.observed_routes?.segments || [])
    .filter((segment) => !identities.has(segment.id)).map((segment) => ({
    id: segment.id, disposition: 'unresolved', points: structuredClone(segment.points),
    completeness: 'partial', elevation_meters: null,
    line_style: segment.line_style ?? 'unknown',
  }))
  // The service may append paths for newly added/classified devices. Saved
  // geometry/tombstones still win for existing identities, never stale copies.
  const persisted = new Map((record.review?.generated_wiring ?? []).map(wire => [wire.id,wire]))
  const generated = (record.generated_wiring ?? record.review?.generated_wiring ?? []).map(wire => {
    const saved = persisted.get(wire.id)
    if (saved?.algorithm === 'astar' && saved.disposition === 'unresolved' && !saved.suppression_reason
      && !saved.device_attachments?.length && !saved.junction_attachments?.length) return wire
    if (wire.suppression_reason === 'redundant_observed_connection' && saved?.disposition === 'unresolved') return wire
    if (saved && wire.installation_method && wire.installation_method !== 'unknown'
      && (!saved.installation_method || saved.installation_method === 'unknown')) {
      return {...saved, installation_method:wire.installation_method, line_style:wire.line_style,
        wiring_legend_id:wire.wiring_legend_id, wiring_legend_name:wire.wiring_legend_name}
    }
    return saved ?? wire
  })
  for (const [id,wire] of persisted) if (!generated.some(item => item.id===id)) generated.push(wire)
  return [...saved, ...missing, ...structuredClone(generated).map(wire => ({ ...wire, origin: 'generated' }))]
}

export function wiringSavePayload(wires) {
  return {
    observed_wiring: wires.filter(w => w.origin !== 'generated'),
    generated_wiring: wires.filter(w => w.origin === 'generated').map(wire => {
      const saved = { ...wire }
      delete saved.origin
      return saved
    }),
  }
}

export function parseWiringPoints(text, width, height) {
  const rows = text.trim().split(/\r?\n/)
  if (rows.length < 2 || rows.length > 2048) throw new Error('Enter 2–2048 points, one X,Y pair per line.')
  const number = /^\d+(?:\.\d+)?$/
  const points = rows.map((row) => {
    const values = row.split(',').map((value) => value.trim())
    if (values.length !== 2 || !values.every((value) => number.test(value))) {
      throw new Error('Each point needs two finite, nonnegative numbers: X,Y.')
    }
    const [x, y] = values.map(Number)
    if (!Number.isFinite(x) || !Number.isFinite(y) || x > width || y > height) {
      throw new Error(`Points must stay within the source page: 0–${width} X, 0–${height} Y.`)
    }
    return { x, y }
  })
  if (points.some((point, index) => index && point.x === points[index - 1].x && point.y === points[index - 1].y)) {
    throw new Error('Consecutive points must differ.')
  }
  return points
}

export function nextWiringId(wires) {
  const last = Math.max(0, ...wires.filter((wire) => /^manual-wiring-\d{4}$/.test(wire.id))
    .map((wire) => Number(wire.id.slice(-4))))
  if (last >= 9999) throw new Error('Manual wiring identity limit reached.')
  return `manual-wiring-${String(last + 1).padStart(4, '0')}`
}
