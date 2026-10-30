// Shared path records remain the editable edges. Only explicit attachments
// identify shared nodes; geometric intersections are never graph connections.
import { nextWiringId } from './observedWiringDraft.js'
import { joinWireJunction, inheritWireAssignments } from './wireJunctions.js'
import { mergedWireAssignments } from './wireAssignments.js'

export const activeWire = w => w.disposition !== 'rejected' && !w.suppression_reason
export const vertexIds = w => w.vertex_ids || w.points.map((_, i) => `${w.id}:vertex:${i}`)
export const compatibleWires = (a, b) =>
  (a.circuit_id ?? null) === (b.circuit_id ?? null)
  && (a.elevation_meters ?? null) === (b.elevation_meters ?? null)
  && (a.height_above_floor_meters ?? null) === (b.height_above_floor_meters ?? null)
  && (a.installation_method || 'unknown') === (b.installation_method || 'unknown')

export function wiringComponents(wires) {
  const active = wires.filter(activeWire), parents = new Map(active.map(w => [w.id, w.id])), nodes = new Map()
  const root = id => { while (parents.get(id) !== id) id = parents.get(id); return id }
  for (const w of active) {
    const contacts = [
      ...(w.junction_attachments || []).map(a => ({...a, key:`junction:${a.junction_id}`})),
      ...(w.device_attachments || []).filter(a => a.terminal_id).map(a => ({...a,key:`terminal:${a.symbol_id}:${a.terminal_id}`})),
    ]
    for (const a of contacts) {
      const point = w.points[a.point_index]
      if (!point) throw new Error('Connection vertex is unavailable.')
      const previous = nodes.get(a.key)
      if (previous) {
        // Historical unspecified terminals stay isolated; explicit conflicting
        // assignments cannot be silently reconciled by connectivity.
        if (!compatibleWires(w, previous.w) || point.x !== previous.point.x || point.y !== previous.point.y) {
          throw new Error('Connected paths require matching circuit, height and installation.')
        }
        const roots = [root(w.id), root(previous.w.id)].sort()
        parents.set(roots[1], roots[0])
      } else nodes.set(a.key, {w,point})
    }
  }
  return new Map(active.map(w => [w.id,root(w.id)]))
}

export function appendDrawingVertex(vertices, point, snap = null) {
  if (vertices.length>=2048) return vertices
  const last = vertices.at(-1)?.point
  if (last && Math.hypot(last.x-point.x,last.y-point.y) < 1e-6) return vertices
  // Loops are allowed, retracing an already committed physical span is not.
  if (last && vertices.slice(1).some((v,i) =>
    (v.point.x === point.x && v.point.y === point.y && vertices[i].point.x === last.x && vertices[i].point.y === last.y)
    || (v.point.x === last.x && v.point.y === last.y && vertices[i].point.x === point.x && vertices[i].point.y === point.y))) return vertices
  return [...vertices,{point:{...point},snap: snap?.snapped ? snap : null}]
}

export function commitWiringPath(draft, vertices, attributes) {
  if (vertices.length < 2) return draft
  const id = nextWiringId(draft.wirings)
  let wire = {id, disposition:'added',completeness:'partial',elevation_meters:null,path_origin:'manual',...attributes,
    points:vertices.map(v => ({...v.point})),device_attachments:[]}
  wire.vertex_ids = wire.points.map((p,i)=>`${id}:vertex:${wire.points.findIndex(q=>q.x===p.x && q.y===p.y) ?? i}`)
  let next = {...draft,wirings:[...draft.wirings,wire]}
  // A newly drawn extension takes the target network's assignments rather than
  // the toolbar's initial placement suggestion. Conflicting targets still fail.
  const targets = vertices.flatMap(({snap}) => !snap ? [] : snap.kind === 'wire'
    ? draft.wirings.filter(w => activeWire(w) && w.id === snap.id)
    : snap.kind === 'device' ? draft.wirings.filter(w => activeWire(w) && (w.device_attachments || []).some(a =>
      a.symbol_id === snap.id && (!snap.terminalId || a.terminal_id === snap.terminalId))) : [])
  if (targets.length) {
    const assignments = mergedWireAssignments(targets)
    if (!assignments || (attributes.circuit_id && assignments.circuit_id && attributes.circuit_id !== assignments.circuit_id)) {
      throw new Error('Choose endpoints on the same circuit and wiring placement.')
    }
    wire = {...wire,...assignments}
    next = {...next,wirings:next.wirings.map(w => w.id === id ? wire : w)}
    next = inheritWireAssignments(next, [id,...targets.map(w => w.id)])
  }
  // Reproject against current geometry: two snaps may split the same original edge.
  for (let i = 0; i < vertices.length; i++) {
    const snap = vertices[i].snap
    if (!snap) continue
    if (snap.kind === 'device') {
      const symbol = draft.symbols.find(s => s.id === snap.id && s.disposition !== 'rejected')
      if (!symbol || symbol.center.x !== snap.x || symbol.center.y !== snap.y) throw new Error('Device moved; draw the connection again.')
      // A manual click explicitly selects this design anchor. It is not a
      // detected electrical pin assignment or a conductor-count inference.
      const known=[...new Set(draft.wirings.filter(activeWire).flatMap(w=>(w.device_attachments || [])
        .filter(a=>a.symbol_id===symbol.id && a.terminal_id).map(a=>a.terminal_id)))]
      if(!snap.terminalId && known.length>1)throw new Error('This device has distinct terminals. Extend the intended wire endpoint instead.')
      const terminal = snap.terminalId || known[0] || 'design-anchor'
      if (next.wirings.filter(activeWire).some(w => (w.device_attachments || []).some(a =>
        a.symbol_id === symbol.id && a.terminal_id === terminal) && !compatibleWires(w,wire))) {
        throw new Error('Cannot join different circuits, heights or installation methods.')
      }
      next = {...next,wirings:next.wirings.map(w => w.id === id ? {...w,device_attachments:[...w.device_attachments,
        {symbol_id:symbol.id,point_index:i,terminal_id:terminal}]} : w)}
    } else if (snap.kind === 'wire') {
      const target = next.wirings.find(w => w.id === snap.id && activeWire(w))
      if (!target || !compatibleWires(wire,target)) throw new Error('Cannot join different circuits, heights or installation methods.')
      let found = false
      for (let edge = 0; edge < target.points.length-1; edge++) {
        const a=target.points[edge], b=target.points[edge+1], dx=b.x-a.x,dy=b.y-a.y, l=dx*dx+dy*dy
        if (!l) continue
        const t=((snap.x-a.x)*dx+(snap.y-a.y)*dy)/l
        if (t < -1e-8 || t > 1+1e-8 || Math.hypot(a.x+t*dx-snap.x,a.y+t*dy-snap.y)>1e-6) continue
        const vertex=t<1e-8?edge:t>1-1e-8?edge+1:null
        const binding=target.device_attachments?.find(c => c.point_index === vertex)
        if (binding) {
          if (!binding.terminal_id) throw new Error('This historical device terminal is unspecified. Choose an unbound wire point.')
          next={...next,wirings:next.wirings.map(w=>w.id===id?{...w,device_attachments:[...w.device_attachments,{...binding,point_index:i,
            provenance:'designer_attachment',source_connection_id:undefined,source_candidate_run_id:undefined,evidence_kind:undefined,observed_anchor:undefined}]}:w)}
        } else next=joinWireJunction(next,id,i,target.id,edge,t<1e-8?0:t>1-1e-8?1:t)
        found=true;break
      }
      if (!found) throw new Error('Wire moved; draw the connection again.')
    }
  }
  const components=wiringComponents(next.wirings)
  const members=next.wirings.filter(w=>components.get(w.id)===components.get(id))
  const lineage=[...new Set(members.flatMap(w=>[w.id,...(w.network_lineage || [])]))].sort()
  return {...next,wirings:next.wirings.map(w=>members.includes(w)?{...w,network_lineage:lineage}:w)}
}
