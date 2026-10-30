// Diagnostic comparison only; no quantity, connectivity or approval mutations.
export function wiringCheck(wires,segments=[],symbols) {
  const source=new Map(segments.map(s=>[s.id,s]))
  const devices=symbols ? new Set(symbols.filter(s=>s.disposition!=='rejected').map(s=>s.id)):null
  return wires.filter(w=>w.disposition!=='rejected' && !w.suppression_reason).map(w=>{
    const contacts=w.device_attachments || []
    const occupied=new Set([...contacts.filter(a=>!devices || devices.has(a.symbol_id)),...(w.junction_attachments || [])].map(a=>a.point_index))
    const open=[0,w.points.length-1].filter(i=>!occupied.has(i))
    const original=source.get(w.id)
    return {wire:w,open,broken:Boolean(devices && contacts.some(a=>!devices.has(a.symbol_id))),changed:Boolean(original && JSON.stringify(original.points)!==JSON.stringify(w.points)),
      proposal:w.origin==='generated' && !['accepted','corrected','added'].includes(w.disposition)}
  })
}
