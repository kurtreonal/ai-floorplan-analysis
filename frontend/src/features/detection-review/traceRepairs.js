import { activeWire, compatibleWires } from './connectedWiring.js'

// A repair suggestion only. Never merge merely nearby lines, different circuits,
// manual routes or generated proposals into a source trace.
export function duplicateSourceTraces(wires) {
  const source=wires.filter(w=>activeWire(w)&&/^segment-\d+$/.test(w.id)&&w.origin!=='generated')
  if(source.length>512||source.reduce((n,w)=>n+w.points.length,0)>8192)return []
  const length=w=>w.points.slice(1).reduce((n,p,i)=>n+Math.hypot(p.x-w.points[i].x,p.y-w.points[i].y),0)
  function covered(a,b,target){
    const dx=b.x-a.x,dy=b.y-a.y,size=Math.hypot(dx,dy);if(!size)return true
    const spans=[]
    for(let i=1;i<target.points.length;i++){
      const c=target.points[i-1],d=target.points[i]
      if(Math.max(Math.abs((c.x-a.x)*dy-(c.y-a.y)*dx),Math.abs((d.x-a.x)*dy-(d.y-a.y)*dx))/size>.01)continue
      const lo=((c.x-a.x)*dx+(c.y-a.y)*dy)/size,hi=((d.x-a.x)*dx+(d.y-a.y)*dy)/size
      spans.push([Math.min(lo,hi),Math.max(lo,hi)])
    }
    let end=0
    for(const [lo,hi] of spans.sort((x,y)=>x[0]-y[0])){if(hi<end)continue;if(lo>end+.01)return false;end=Math.max(end,hi);if(end>=size-.01)return true}
    return false
  }
  const kept=[],duplicates=[]
  for(const wire of [...source].sort((a,b)=>length(b)-length(a)||a.id.localeCompare(b.id))){
    const target=kept.find(other=>compatibleWires(wire,other)&&wire.line_style===other.line_style
      &&wire.points.slice(1).every((p,i)=>covered(wire.points[i],p,other))
      &&(wire.device_attachments||[]).every(a=>(other.device_attachments||[]).some(b=>a.symbol_id===b.symbol_id&&a.terminal_id===b.terminal_id&&JSON.stringify(wire.points[a.point_index])===JSON.stringify(other.points[b.point_index])))
      &&(wire.junction_attachments||[]).every(a=>(other.junction_attachments||[]).some(b=>a.junction_id===b.junction_id&&JSON.stringify(wire.points[a.point_index])===JSON.stringify(other.points[b.point_index]))))
    if(target)duplicates.push({id:wire.id,retainedId:target.id});else kept.push(wire)
  }
  return duplicates
}
