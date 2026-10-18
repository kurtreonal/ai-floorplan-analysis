import { vertexIds, wiringComponents } from './connectedWiring.js'
const active = wire => wire.disposition !== 'rejected' && !wire.suppression_reason
const changed = wire => ({ ...wire, disposition: wire.disposition === 'added' ? 'added' : 'corrected' })
const at = (wire, index) => wire.junction_attachments?.find(a => a.point_index === index)
const samePoint = (a, b) => a.x === b.x && a.y === b.y

export function wireJunctions(draft) {
  const nodes = new Map()
  for (const wire of draft.wirings || []) if (active(wire)) {
    for (const contact of wire.junction_attachments || []) {
      const point = wire.points[contact.point_index]
      if (!point || wire.device_attachments?.some(a => a.point_index === contact.point_index)) throw new Error('Invalid junction vertex.')
      if (!nodes.has(contact.junction_id)) nodes.set(contact.junction_id, [])
      nodes.get(contact.junction_id).push({ wire, index: contact.point_index, point })
    }
  }
  for (const members of nodes.values()) {
    const first = members[0]
    if (new Set(members.map(m => m.wire.id)).size < 2) throw new Error('A junction requires two active paths.')
    if (members.some(m => !samePoint(m.point, first.point)
      || (m.wire.circuit_id ?? null) !== (first.wire.circuit_id ?? null)
      || (m.wire.elevation_meters ?? null) !== (first.wire.elevation_meters ?? null)
      || (m.wire.installation_method || 'unknown') !== (first.wire.installation_method || 'unknown'))) {
      throw new Error('Joined paths require the same position, circuit, height and installation method. Review their assignments first.')
    }
  }
  return nodes
}

export function connectedWireIds(draft, wireId) {
  const components = wiringComponents(draft.wirings || [])
  return new Set([...components].filter(([,root])=>root===components.get(wireId)).map(([id])=>id))
}

function validateResult(draft) {
  if (draft.wirings.some(w => active(w) && w.points.some((p, i) => i && samePoint(p, w.points[i-1])))) {
    throw new Error('This edit would collapse a wiring segment.')
  }
  wireJunctions(draft)
  wiringComponents(draft.wirings)
  return draft
}

function reindex(wire, index, delta, point) {
  const points = [...wire.points]
  const ids = [...vertexIds(wire)]
  if (delta === 1) {
    // A deleted vertex may remain in an older immutable review. Do not reuse
    // its identity for a new node after deletion and reload.
    ids.splice(index,0,`${wire.id}:vertex:${globalThis.crypto.randomUUID()}`)
  } else ids.splice(index,1)
  if (delta === 1) points.splice(index, 0, point)
  else points.splice(index, 1)
  const shift = rows => (rows || []).filter(a => delta === 1 || a.point_index !== index)
    .map(a => ({ ...a, point_index: a.point_index >= index ? a.point_index + delta : a.point_index }))
  return changed({ ...wire, points, vertex_ids:ids, device_attachments: shift(wire.device_attachments), junction_attachments: shift(wire.junction_attachments),
    auto_connect_disabled_endpoints: (wire.auto_connect_disabled_endpoints || []).filter(i => delta === 1 || i !== index).map(i => i >= index ? i+delta : i) })
}

export function insertWireVertex(draft, wireId, segmentIndex, t = .5) {
  const wire = draft.wirings.find(w => w.id === wireId && active(w))
  if (!wire || wire.points.length >= 2048 || !Number.isInteger(segmentIndex) || segmentIndex < 0 || segmentIndex >= wire.points.length-1
    || !Number.isFinite(t) || t <= 0 || t >= 1) throw new Error('Choose a valid segment and an interior position.')
  const a = wire.points[segmentIndex], b = wire.points[segmentIndex+1]
  const point = { x: a.x+(b.x-a.x)*t, y: a.y+(b.y-a.y)*t }
  return validateResult({ ...draft, wirings: draft.wirings.map(w => w.id === wireId ? reindex(w, segmentIndex+1, 1, point) : w) })
}

export function deleteWireVertex(draft, wireId, index) {
  const wire = draft.wirings.find(w => w.id === wireId && active(w))
  if (!wire || wire.points.length <= 2 || !Number.isInteger(index) || index < 0 || index >= wire.points.length) throw new Error('A path needs at least two vertices.')
  if (at(wire, index) || wire.device_attachments?.some(a => a.point_index === index)) throw new Error('Disconnect this vertex before deleting it.')
  return validateResult({ ...draft, wirings: draft.wirings.map(w => w.id === wireId ? reindex(w, index, -1) : w) })
}

export function moveJunctionVertex(draft, wireId, index, point) {
  const wire = draft.wirings.find(w => w.id === wireId && active(w))
  const contact = wire && at(wire, index)
  if (!contact) return null
  const nodes = wireJunctions(draft).get(contact.junction_id)
  const next = { ...draft, wirings: draft.wirings.map(w => {
    const indices = nodes.filter(n => n.wire.id === w.id).map(n => n.index)
    const identities=new Set(indices.map(i=>w.vertex_ids?.[i]).filter(Boolean))
    w.vertex_ids?.forEach((id,i)=>{if(identities.has(id)&&!indices.includes(i))indices.push(i)})
    return indices.length ? changed({ ...w, points: w.points.map((p, i) => indices.includes(i) ? { ...point } : p) }) : w
  }) }
  return validateResult(next)
}

export function joinWireJunction(draft, sourceId, sourceIndex, targetId, segmentIndex, t) {
  const source = draft.wirings.find(w => w.id === sourceId && active(w))
  let target = draft.wirings.find(w => w.id === targetId && active(w))
  if (!source || !target || sourceId === targetId || !source.points[sourceIndex] || !Number.isInteger(sourceIndex)
    || source.device_attachments?.some(a => a.point_index === sourceIndex)) throw new Error('Choose an unattached source vertex and a different active path.')
  if ((source.origin === 'generated') !== (target.origin === 'generated')) throw new Error('Use measured circuit planning to attach generated routes to observed wiring; their draft review lifecycles must stay separate.')
  if (!Number.isInteger(segmentIndex) || segmentIndex < 0 || segmentIndex >= target.points.length-1 || !Number.isFinite(t) || t < 0 || t > 1) {
    throw new Error('Choose a target segment and a position between 0% and 100%.')
  }
  let next = draft
  const index = segmentIndex + (t === 0 ? 0 : 1)
  if (t > 0 && t < 1) { next = insertWireVertex(draft, targetId, segmentIndex, t); target = next.wirings.find(w => w.id === targetId) }
  if (target.device_attachments?.some(a => a.point_index === index)) throw new Error('Choose a wire vertex without a device terminal binding.')
  if ((source.circuit_id ?? null) !== (target.circuit_id ?? null)
    || (source.elevation_meters ?? null) !== (target.elevation_meters ?? null)
    || (source.installation_method || 'unknown') !== (target.installation_method || 'unknown')) {
    throw new Error('Circuit, height and installation must match explicitly; paths were not merged.')
  }
  const oldSource = at(source, sourceIndex)?.junction_id, oldTarget = at(target, index)?.junction_id
  const numbers = next.wirings.flatMap(w => (w.junction_attachments || []).map(a => Number(a.junction_id.slice(9))))
  const number = Math.max(0, ...numbers)+1
  if (!oldSource && !oldTarget && number > 9999) throw new Error('Junction identity limit reached.')
  const identity = oldTarget || oldSource || `junction-${String(number).padStart(4, '0')}`
  const lineage = [...new Set([...connectedWireIds(next,sourceId),...connectedWireIds(next,targetId),
    ...(source.network_lineage || []),...(target.network_lineage || [])])].sort()
  const merged = new Set([oldSource, oldTarget].filter(Boolean)), point = target.points[index]
  next = { ...next, wirings: next.wirings.map(w => {
    if (!active(w)) return w
    let contacts = w.junction_attachments || []
    if (w.id === sourceId && !at(w, sourceIndex)) contacts = [...contacts, {junction_id:identity,point_index:sourceIndex}]
    if (w.id === targetId && !at(w, index)) contacts = [...contacts, {junction_id:identity,point_index:index}]
    contacts = contacts.map(a => merged.has(a.junction_id) ? {...a,junction_id:identity} : a)
    const indices = contacts.filter(a => a.junction_id === identity).map(a => a.point_index)
    return indices.length ? changed({ ...w, network_lineage:lineage, junction_attachments: contacts, points: w.points.map((p, i) => indices.includes(i) ? {...point} : p) }) : w
  }) }
  return validateResult(next)
}

export function detachWireJunction(draft, wireId, index = null) {
  let wires = draft.wirings.map(w => w.id === wireId ? changed({ ...w,
    junction_attachments:(w.junction_attachments || []).filter(a => index !== null && a.point_index !== index) }) : w)
  const members = new Map()
  for (const w of wires.filter(active)) for (const a of w.junction_attachments || []) {
    if (!members.has(a.junction_id)) members.set(a.junction_id,new Set())
    members.get(a.junction_id).add(w.id)
  }
  wires = wires.map(w => {
    const original = draft.wirings.find(v => v.id === w.id)
    const contacts = (w.junction_attachments || []).filter(a => members.get(a.junction_id)?.size >= 2)
    const removed = (original.junction_attachments || []).filter(a => !contacts.some(b => a.point_index === b.point_index))
    return removed.length ? changed({ ...w, junction_attachments: contacts,
      auto_connect_disabled_endpoints:[...new Set([...(w.auto_connect_disabled_endpoints || []),...removed.map(a=>a.point_index)])] }) : w
  })
  return validateResult({ ...draft, wirings: wires })
}

export function updateWireNetwork(draft, replacement) {
  const original = draft.wirings.find(w => w.id === replacement.id)
  if (replacement.disposition === 'rejected') {
    const next = detachWireJunction(draft, replacement.id)
    return { ...next, wirings: next.wirings.map(w => w.id === replacement.id ? {...w,disposition:'rejected'} : w) }
  }
  const ids = connectedWireIds(draft, replacement.id)
  const keys = ['circuit_id','elevation_meters','installation_method','line_style','wiring_legend_id','wiring_legend_name']
    .filter(key => replacement[key] !== original[key])
  const patch = Object.fromEntries(keys.map(key => [key,replacement[key]]))
  return validateResult({ ...draft, wirings: draft.wirings.map(w => w.id === replacement.id ? replacement
    : ids.has(w.id) && keys.length ? changed({...w,...patch}) : w) })
}
