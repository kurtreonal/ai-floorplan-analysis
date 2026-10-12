// Interior half-edge convention inspired by Blueprint3D Modern half_edge.ts.
// Only explicit closed endpoint topology defines a room face. Never infer
// closure from proximity or silently describe an open wall as an interior edge.
import { wallLength } from './wallDrawing.js'

const key=p=>`${p.x},${p.y}`
const vector=(a,b)=>({x:b.x-a.x,y:b.y-a.y})
const cross=(a,b)=>a.x*b.y-a.y*b.x
function offsetIntersection(previous,current,thickness) {
  const a=vector(previous.start,previous.end),b=vector(current.start,current.end),al=Math.hypot(a.x,a.y),bl=Math.hypot(b.x,b.y)
  const p={x:current.start.x-a.y/al*thickness(previous)/2,y:current.start.y+a.x/al*thickness(previous)/2}
  const q={x:current.start.x-b.y/bl*thickness(current)/2,y:current.start.y+b.x/bl*thickness(current)/2}
  const den=cross(a,b)
  if(Math.abs(den)<1e-8)return q
  const t=cross(vector(p,q),b)/den
  const result={x:p.x+t*a.x,y:p.y+t*a.y}
  // Degenerate acute corners cannot produce unbounded measurement spikes.
  return Math.hypot(result.x-q.x,result.y-q.y)<Math.min(al,bl)/2 ? result : q
}

export function wallMeasurements(walls,thickness=w=>w.estimated_thickness_pixels??12) {
  const result=new Map(walls.map(w=>[w.id,{length:wallLength(w),center:{x:(w.start.x+w.end.x)/2,y:(w.start.y+w.end.y)/2},basis:'centerline'}]))
  const edges=walls.filter(w=>w.disposition!=='rejected'&&wallLength(w)>1e-6).flatMap(w=>[
    {...w,direction:0},{...w,start:w.end,end:w.start,direction:1}])
  const outgoing=new Map()
  for(const edge of edges){const k=key(edge.start);if(!outgoing.has(k))outgoing.set(k,[]);outgoing.get(k).push(edge)}
  const visited=new Set()
  for(const first of edges) {
    const chain=[];let edge=first
    for(let i=0;i<=edges.length;i++) {
      const id=`${edge.id}:${edge.direction}`
      if(visited.has(id))break
      visited.add(id);chain.push(edge)
      const back=Math.atan2(edge.start.y-edge.end.y,edge.start.x-edge.end.x)
      const choices=(outgoing.get(key(edge.end))||[]).filter(e=>e.id!==edge.id)
      if(!choices.length)break
      const turn=e=>(back-Math.atan2(e.end.y-e.start.y,e.end.x-e.start.x)+Math.PI*2)%(Math.PI*2)
      edge=choices.sort((a,b)=>turn(a)-turn(b))[0]
      if(edge===first) {
        const area=chain.reduce((s,e)=>s+cross(e.start,e.end),0)/2
        if(area<=1e-6)break // Unbounded exterior face, not a room interior.
        const corners=chain.map((e,i)=>offsetIntersection(chain[(i+chain.length-1)%chain.length],e,thickness))
        chain.forEach((e,i)=>{
          const a=corners[i],b=corners[(i+1)%corners.length],length=Math.hypot(b.x-a.x,b.y-a.y)
          const old=result.get(e.id)
          if(length>0&&(old.basis==='centerline'||length<old.length))result.set(e.id,{length,center:{x:(a.x+b.x)/2,y:(a.y+b.y)/2},basis:'interior'})
        })
        break
      }
    }
  }
  return result
}

export function formatWallMeasure(length,pixelsPerMeter,unit='m') {
  if(!Number.isFinite(pixelsPerMeter)||pixelsPerMeter<=0)return `${Math.round(length*100)/100} px (unscaled)`
  const m=length/pixelsPerMeter
  if(unit==='ft'){const total=Math.round(m/0.0254);return `${Math.floor(total/12)}'${total%12}"`}
  const factor={m:1,cm:100,mm:1000}[unit]??1
  return `${Number((m*factor).toFixed(3))} ${unit}`
}
