// Interaction adapted from Blueprint3D Modern floorplanner.ts / corner.ts,
// commit f56f0b2a4a6e177181aefbf535d2945b937b5c02. See THIRD_PARTY_NOTICES.
import { wallContacts, moveJoinedWall } from '../../geometry/wallTopology.js'
import { findSnapPoint, constrainPoint } from './wallEditorUtils.js'
import { moveConnectedDevice } from './deviceConnections.js'

const EPS = 1e-6
const active = w => w.disposition !== 'rejected'
const distance = (a,b) => Math.hypot(a.x-b.x,a.y-b.y)
const point = (a,b,t) => ({x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t})
const projection = (p,w) => ((p.x-w.start.x)*(w.end.x-w.start.x)+(p.y-w.start.y)*(w.end.y-w.start.y))/distance(w.start,w.end)**2
const onWall = (p,w) => { const t=projection(p,w); return t>=-EPS&&t<=1+EPS&&distance(p,point(w.start,w.end,t))<EPS }

export function wallPointerTarget(raw,walls,{scale=1,anchor=null,excludeWallId=null,shift=false}={}) {
  // Reference: 20 cm corner merge, 25 cm axis alignment, at 15 px/foot.
  // Convert once to reference screen pixels, then undo VED viewport zoom.
  const threshold=(20*15/30.48)/scale,alignmentThreshold=(25*15/30.48)/scale
  const constrained=shift&&anchor ? constrainPoint(anchor,raw,true) : raw
  const snap=findSnapPoint(constrained,walls,{threshold,excludeWallId})
  if(snap.snapped)return {point:{x:snap.x,y:snap.y},snapped:true,guides:[]}
  const corners=[...(anchor?[anchor]:[]),...walls.filter(w=>active(w)&&w.id!==excludeWallId).flatMap(w=>[w.start,w.end])]
  const result={...constrained},guides=[]
  for(const axis of ['x','y']) {
    const closest=corners.filter(p=>Math.abs(p[axis]-constrained[axis])<=alignmentThreshold)
      .sort((a,b)=>Math.abs(a[axis]-constrained[axis])-Math.abs(b[axis]-constrained[axis]))[0]
    if(closest){result[axis]=closest[axis];guides.push({from:closest,to:result,axis})}
  }
  return {point:result,snapped:guides.length>0,guides}
}

function allocator(walls) {
  let n=Math.max(0,...walls.filter(w=>w.id.startsWith('manual-wall-')).map(w=>Number(w.id.slice(12))))
  return ()=>`manual-wall-${String(++n).padStart(4,'0')}`
}

// Draft opening records have coordinates, not wall IDs. Protect opening spans
// before a split; preserve these records verbatim. No inferred opening deletion.
function protectOpening(draft,wall,at) {
  return [...(draft.openings||[]),...(draft.source_openings||[])].some(o=>active(o)&&o.points?.length>=2&&o.points.every(p=>onWall(p,wall))&&
    at>Math.min(...o.points.map(p=>projection(p,wall)))+EPS&&at<Math.max(...o.points.map(p=>projection(p,wall)))-EPS)
}

function splitAt(draft,wallId,p,nextId) {
  const wall=draft.walls.find(w=>w.id===wallId),t=projection(p,wall)
  if(t<=EPS||t>=1-EPS)return draft
  if(protectOpening(draft,wall,t))throw new Error('Cannot split through a saved door/window opening. Choose its boundary instead.')
  const id=nextId(),end=wall.end
  return {...draft,walls:draft.walls.flatMap(w=>w.id===wallId ? [{...w,end:p},{...w,id,start:p,end,disposition:'added'}] : [w]),
    symbols:(draft.symbols||[]).map(s=>s.mounting_wall_id===wallId&&projection(s.center,wall)>t ? {...s,mounting_wall_id:id} : s)}
}

export function addConnectedWall(draft,wall) {
  if(distance(wall.start,wall.end)<EPS)return draft
  // Reject retracing any occupied collinear span; no hidden duplicate surfaces.
  if(draft.walls.some(w=>active(w)&&wallContacts(wall,w).length===2&&
    distance(...wallContacts(wall,w).map(c=>c.point))>EPS))throw new Error('A wall already occupies part of this span.')
  const nextId=allocator(draft.walls)
  let next=draft
  const junctions=[{point:wall.start,t:0},{point:wall.end,t:1},...draft.walls.filter(active).flatMap(w=>wallContacts(wall,w))]
    .sort((a,b)=>a.t-b.t).filter((c,i,all)=>i===0||Math.abs(c.t-all[i-1].t)>EPS)
  for(const contact of junctions)for(const w of [...next.walls])if(active(w)&&onWall(contact.point,w))next=splitAt(next,w.id,contact.point,nextId)
  const pieces=junctions.slice(1).map((c,i)=>({...wall,start:junctions[i].point,end:c.point,id:nextId(),disposition:'added'}))
  if(next.walls.filter(active).length+pieces.length>512)throw new Error('Wall editing exceeds the bounded 512-wall geometry budget.')
  return {...next,walls:[...next.walls,...pieces]}
}

export function moveConnectedWall(draft,wall,options={}) {
  let next={...draft,walls:moveJoinedWall(draft.walls,wall,options)}
  const changed=draft.walls.filter(w=>active(w)&&next.walls.some(n=>n.id===w.id&&(distance(n.start,w.start)>EPS||distance(n.end,w.end)>EPS)))
  if(changed.some(w=>(draft.source_openings||[]).some(o=>o.points.every(p=>onWall(p,w))&&
    !(draft.openings||[]).some(review=>review.id===o.id))))throw new Error('Review the detected opening before moving its supporting wall.')
  if(changed.some(w=>distance(next.walls.find(n=>n.id===w.id).start,next.walls.find(n=>n.id===w.id).end)<EPS))throw new Error('Wall edit would collapse a connected segment.')
  for(const old of changed) {
    const updated=next.walls.find(w=>w.id===old.id)
    for(const other of next.walls.filter(w=>active(w)&&w.id!==old.id)) {
      const contacts=wallContacts(updated,other)
      if(contacts.length===2&&distance(contacts[0].point,contacts[1].point)>EPS) {
        const prior=wallContacts(old,draft.walls.find(w=>w.id===other.id))
        if(prior.length!==2||distance(...prior.map(c=>c.point))+EPS<distance(...contacts.map(c=>c.point)))throw new Error('Wall edit would overlap an existing wall.')
      }
    }
  }
  // Opening points move only with their uniquely identified supporting wall.
  next.openings=(draft.openings||[]).map(o=>{
    const supports=changed.filter(w=>o.points?.every(p=>onWall(p,w)))
    if(supports.length!==1)return o
    const old=supports[0],updated=next.walls.find(w=>w.id===old.id)
    const center={x:o.points.reduce((s,p)=>s+p.x,0)/o.points.length,y:o.points.reduce((s,p)=>s+p.y,0)/o.points.length}
    const target=point(updated.start,updated.end,projection(center,old))
    const angle=Math.atan2(updated.end.y-updated.start.y,updated.end.x-updated.start.x)-Math.atan2(old.end.y-old.start.y,old.end.x-old.start.x)
    const points=o.points.map(p=>({x:target.x+(p.x-center.x)*Math.cos(angle)-(p.y-center.y)*Math.sin(angle),
      y:target.y+(p.x-center.x)*Math.sin(angle)+(p.y-center.y)*Math.cos(angle)}))
    if(!points.every(p=>onWall(p,updated)))throw new Error('Wall edit would move its opening outside the wall span.')
    return {...o,points}
  })
  for(const symbol of draft.symbols||[]) {
    const old=changed.find(w=>w.id===symbol.mounting_wall_id)
    if(!old)continue
    const updated=next.walls.find(w=>w.id===old.id),t=projection(symbol.center,old)
    const oldAxis=Math.atan2(old.end.y-old.start.y,old.end.x-old.start.x)
    const newAxis=Math.atan2(updated.end.y-updated.start.y,updated.end.x-updated.start.x)
    const base=point(old.start,old.end,t),target=point(updated.start,updated.end,t),dx=symbol.center.x-base.x,dy=symbol.center.y-base.y,a=newAxis-oldAxis
    const center={x:target.x+dx*Math.cos(a)-dy*Math.sin(a),y:target.y+dx*Math.sin(a)+dy*Math.cos(a)}
    const moved=moveConnectedDevice(next,{...symbol,center})
    if(moved===next&&distance(center,symbol.center)>EPS)throw new Error('Wall movement would collapse an attached wire. Edit that connection first.')
    next=moved
  }
  const nextId=allocator(next.walls)
  for(const p of [wall.start,wall.end])for(const w of [...next.walls])if(active(w)&&w.id!==wall.id&&onWall(p,w))next=splitAt(next,w.id,p,nextId)
  return next
}

export function deleteConnectedWall(draft,id,{detachMounted=false}={}) {
  const wall=draft.walls.find(w=>w.id===id)
  if((!detachMounted&&(draft.symbols||[]).some(s=>active(s)&&s.mounting_wall_id===id))||
    [...(draft.openings||[]),...(draft.source_openings||[])].some(o=>active(o)&&o.points?.every(p=>onWall(p,wall))))
    throw new Error('Detach or reassign mounted devices/openings before deleting their wall.')
  return {...draft,walls:draft.walls.map(w=>w.id===id?{...w,disposition:'rejected'}:w),
    symbols:(draft.symbols||[]).map(s=>active(s)&&s.mounting_wall_id===id ? {...s,mounting_wall_id:null,
      disposition:s.disposition==='added'?'added':'corrected'} : s)}
}

export function resizeWall(wall,length) {
  if(!Number.isFinite(length)||length<=EPS)throw new Error('Enter a positive wall length.')
  const old=distance(wall.start,wall.end)
  return {...wall,end:point(wall.start,wall.end,length/old)} // Start stays anchored.
}

export const wallLength=w=>distance(w.start,w.end)
