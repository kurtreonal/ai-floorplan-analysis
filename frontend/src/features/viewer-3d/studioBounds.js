// Presentation bounds only. Never used by measurements or persistence.
export function studioBounds(scene) {
  const points = []
  const add = p => { if (p?.length === 3 && p.every(Number.isFinite)) points.push(p) }
  for (const wall of scene?.walls || []) {
    if (wall.footprints) for (const polygon of wall.footprints) for (const p of polygon) {
      add([p.x, wall.elevation, p.y]); add([p.x, wall.elevation + wall.height, p.y])
    }
    else if (wall.position && wall.size) {
      const angle = wall.rotation?.[1] || 0
      for (const x of [-1,1]) for (const z of [-1,1]) for (const y of [-1,1]) {
        const dx=x*wall.size[0]/2, dz=z*wall.size[2]/2
        add([wall.position[0]+dx*Math.cos(angle)+dz*Math.sin(angle), wall.position[1]+y*wall.size[1]/2,
          wall.position[2]-dx*Math.sin(angle)+dz*Math.cos(angle)])
      }
    }
  }
  for (const symbol of scene?.symbols || []) add(symbol.position)
  for (const room of scene?.rooms || []) for (const p of room.boundary) add([p.x, scene.elevation, p.y])
  for (const wire of scene?.draftWires || []) for (const p of wire.points || []) add(p)
  for (const segment of scene?.routeSegments || []) { add(segment.start); add(segment.end) }
  if (!points.length) return {target:scene?.target || [0,0,0], extent:scene?.extent || 10,
    width:scene?.width || 10, depth:scene?.depth || 10, floor:scene?.elevation || 0}
  const min=[0,1,2].map(i=>Math.min(...points.map(p=>p[i])))
  const max=[0,1,2].map(i=>Math.max(...points.map(p=>p[i])))
  return {target:min.map((v,i)=>(v+max[i])/2), extent:Math.max(...max.map((v,i)=>v-min[i]),1),
    width:Math.max(max[0]-min[0],1),depth:Math.max(max[2]-min[2],1),floor:scene?.elevation || 0}
}
