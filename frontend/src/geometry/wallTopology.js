// Exact shared centreline topology. No proximity repair, room-box walls or
// measurement inference. The same footprints feed Konva and Three.js.
const EPS=1e-7
const cross=(a,b)=>a.x*b.y-a.y*b.x
const sub=(a,b)=>({x:a.x-b.x,y:a.y-b.y})
const lerp=(a,b,t)=>({x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t})
const area=p=>Math.abs(p.reduce((s,a,i)=>s+cross(a,p[(i+1)%p.length]),0))/2

export function wallContacts(a,b) {
  const u=sub(a.end,a.start),v=sub(b.end,b.start),offset=sub(b.start,a.start),den=cross(u,v)
  if (Math.abs(den)>EPS*Math.hypot(u.x,u.y)*Math.hypot(v.x,v.y)) {
    const t=cross(offset,v)/den,s=cross(offset,u)/den
    return t>=-EPS&&t<=1+EPS&&s>=-EPS&&s<=1+EPS ? [{point:lerp(a.start,a.end,t),t,s}] : []
  }
  if (Math.abs(cross(u,offset))>EPS*Math.hypot(u.x,u.y))return []
  const project=p=>((p.x-a.start.x)*u.x+(p.y-a.start.y)*u.y)/(u.x*u.x+u.y*u.y)
  const low=Math.max(0,Math.min(project(b.start),project(b.end))),high=Math.min(1,Math.max(project(b.start),project(b.end)))
  if (low>high+EPS)return []
  return [...new Set([low,high])].map(t=>({point:lerp(a.start,a.end,t),t,
    s:((lerp(a.start,a.end,t).x-b.start.x)*v.x+(lerp(a.start,a.end,t).y-b.start.y)*v.y)/(v.x*v.x+v.y*v.y)}))
}

function halfPlane(poly,a,b,inside=true) {
  const axis=sub(b,a),sign=inside?1:-1,out=[]
  for(let i=0;i<poly.length;i++) {
    const p=poly[i],q=poly[(i+1)%poly.length],dp=cross(axis,sub(p,a))*sign,dq=cross(axis,sub(q,a))*sign
    if(dp>=-EPS)out.push(p)
    if((dp>EPS&&dq<-EPS)||(dp<-EPS&&dq>EPS))out.push(lerp(p,q,dp/(dp-dq)))
  }
  return out.length>=3&&area(out)>EPS*EPS?out:[]
}
function subtract(poly,clip) {
  let remainder=poly;const pieces=[]
  for(let i=0;i<clip.length&&remainder.length;i++) {
    const a=clip[i],b=clip[(i+1)%clip.length],outside=halfPlane(remainder,a,b,false)
    if(outside.length)pieces.push(outside)
    remainder=halfPlane(remainder,a,b)
  }
  return pieces
}
function rectangle(wall,ends) {
  const u=sub(wall.end,wall.start),length=Math.hypot(u.x,u.y),axis={x:u.x/length,y:u.y/length}
  const half=wall.thickness/2,n={x:-axis.y*half,y:axis.x*half}
  const a=lerp(wall.start,wall.end,ends[0]?-half/length:0),b=lerp(wall.start,wall.end,ends[1]?1+half/length:1)
  return [{x:a.x-n.x,y:a.y-n.y},{x:b.x-n.x,y:b.y-n.y},{x:b.x+n.x,y:b.y+n.y},{x:a.x+n.x,y:a.y+n.y}]
}

export function buildWallTopology(input) {
  const walls=input.filter(w=>w.disposition!=='rejected'&&w.thickness>0&&Math.hypot(w.end.x-w.start.x,w.end.y-w.start.y)>EPS)
  const linked=walls.map(()=>new Set()),ends=walls.map(()=>[false,false]),junctions=[]
  if(walls.length>512)throw new Error('Wall topology exceeds the bounded 512-wall budget.')
  for(let i=0;i<walls.length;i++)for(let j=i+1;j<walls.length;j++) {
    for(const contact of wallContacts(walls[i],walls[j])) {
      // Different heights remain distinct surfaces, not a hidden terrace edge.
      if(walls[i].height!==walls[j].height||walls[i].elevation!==walls[j].elevation)continue
      linked[i].add(j);linked[j].add(i)
      if(Math.abs(contact.t)<EPS)ends[i][0]=true
      if(Math.abs(contact.t-1)<EPS)ends[i][1]=true
      if(Math.abs(contact.s)<EPS)ends[j][0]=true
      if(Math.abs(contact.s-1)<EPS)ends[j][1]=true
      junctions.push({...contact,wallIds:[walls[i].id,walls[j].id]})
    }
  }
  const rectangles=walls.map((w,i)=>rectangle(w,ends[i]))
  const models=walls.map((wall,i)=>{
    let footprints=[rectangles[i]]
    // Disjoint ownership prevents coplanar overlap/z-fighting, retaining IDs.
    for(const j of linked[i])if(j<i)footprints=footprints.flatMap(p=>subtract(p,rectangles[j]))
    // Outline only exterior boundary spans, not interior caps at a junction.
    const boundary=[]
    const rect=rectangles[i]
    for(let edge=0;edge<rect.length;edge++) {
      const a=rect[edge],b=rect[(edge+1)%rect.length],cuts=[0,1]
      for(const j of linked[i])for(let k=0;k<4;k++) {
        const hits=wallContacts({start:a,end:b},{start:rectangles[j][k],end:rectangles[j][(k+1)%4]})
        cuts.push(...hits.map(h=>Math.max(0,Math.min(1,h.t))))
      }
      cuts.sort((x,y)=>x-y)
      for(let k=1;k<cuts.length;k++) {
        if(cuts[k]-cuts[k-1]<EPS)continue
        const mid=lerp(a,b,(cuts[k]+cuts[k-1])/2)
        const hidden=[...linked[i]].some(j=>{
          const sides=rectangles[j].map((p,n)=>cross(sub(rectangles[j][(n+1)%4],p),sub(mid,p)))
          return sides.every(s=>s>EPS)||(j<i&&sides.every(s=>s>=-EPS))
        })
        if(!hidden)boundary.push([lerp(a,b,cuts[k-1]),lerp(a,b,cuts[k])])
      }
    }
    return {...wall,footprints,boundary}
  })
  return {walls:models,junctions}
}

export function moveJoinedWall(input,updated,{detach=false}={}) {
  const old=input.find(w=>w.id===updated.id)
  if(!old)return input
  if(detach)return input.map(w=>w.id===updated.id?updated:w)
  updated={...updated}
  // A T branch cannot bend the body of a straight supporting wall. Keep its
  // joined end on that body's existing axis; no nearby wall can acquire it.
  for(const other of input)if(other.id!==old.id&&other.disposition!=='rejected') {
    for(const c of wallContacts(old,other))for(const [end,t] of [['start',0],['end',1]]) {
      if(Math.abs(c.t-t)>EPS||c.s<=EPS||c.s>=1-EPS)continue
      const axis=sub(other.end,other.start),p=updated[end],length=axis.x*axis.x+axis.y*axis.y
      const projection=((p.x-other.start.x)*axis.x+(p.y-other.start.y)*axis.y)/length
      updated[end]=projection>=0&&projection<=1?lerp(other.start,other.end,projection):c.point
    }
  }
  return input.map(w=>{
    if(w.id===updated.id)return updated
    if(w.disposition==='rejected')return w
    const contacts=wallContacts(old,w),next={...w}
    for(const c of contacts)for(const [end,t] of [['start',0],['end',1]]) {
      if(Math.abs(c.s-t)<EPS)next[end]=lerp(updated.start,updated.end,c.t)
    }
    return next
  })
}

export function sceneWallTopology(walls) {
  const topology=buildWallTopology(walls.map(w=>{
    const axis={x:Math.cos(-w.rotation[1]),y:Math.sin(-w.rotation[1])},half=w.size[0]/2
    return {...w,start:{x:w.position[0]-axis.x*half,y:w.position[2]-axis.y*half},
      end:{x:w.position[0]+axis.x*half,y:w.position[2]+axis.y*half},
      thickness:w.size[2],height:w.size[1],elevation:w.position[1]-w.size[1]/2}
  }))
  return topology
}
