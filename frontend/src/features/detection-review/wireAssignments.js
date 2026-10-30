// Unknown assignments may inherit; two explicit, conflicting values never merge.
const fields = ['circuit_id', 'elevation_meters', 'height_above_floor_meters', 'installation_method']
const value = (wire, key) => key === 'installation_method' ? (wire[key] === 'unknown' ? null : wire[key] ?? null) : wire[key] ?? null

export function mergedWireAssignments(wires) {
  if (wires.some(w => w.installation_method && !['unknown','concealed_under_floor','concealed_in_ceiling'].includes(w.installation_method))) return null
  const patch = {}
  for (const key of fields) {
    const explicit = [...new Set(wires.map(w => value(w, key)).filter(v => v !== null))]
    if (explicit.length > 1) return null
    patch[key] = explicit[0] ?? (key === 'installation_method' ? 'unknown' : null)
  }
  return patch
}

export const wireAssignmentSignature = wire => JSON.stringify(fields.map(key => value(wire,key)))

export function predominantWireMethod(wires = []) {
  const counts = new Map()
  for (const wire of wires) if (wire.disposition !== 'rejected' && !wire.suppression_reason && wire.installation_method && wire.installation_method !== 'unknown') {
    counts.set(wire.installation_method, (counts.get(wire.installation_method) || 0) + 1)
  }
  const sorted = [...counts].sort((a, b) => b[1] - a[1])
  return sorted.length && (!sorted[1] || sorted[0][1] > sorted[1][1]) ? sorted[0][0] : 'unknown'
}

export function resolveConnectedProposals(draft) {
  return {...draft,wirings:draft.wirings.map(w => {
    if (w.assignment_state !== 'unresolved' || !w.installation_method || w.installation_method === 'unknown') return w
    const bound = new Set([...(w.device_attachments || []),...(w.junction_attachments || [])].map(a => a.point_index))
    // Explicit designer connections at BOTH ends resolve the geometric draft;
    // proximity or a source/target label alone never counts as a connection.
    return bound.has(0) && bound.has(w.points.length-1) ? {...w,assignment_state:null,disposition:w.disposition==='added'?'added':'corrected'} : w
  })}
}
