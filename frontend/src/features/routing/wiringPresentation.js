import { CurvePath, LineCurve3, QuadraticBezierCurve3, Vector3 } from 'three'

const EPS = 1e-6
const same = (a, b) => a.every((v, i) => Math.abs(v - b[i]) <= EPS)
const finite = p => Array.isArray(p) && p.length === 3 && p.every(Number.isFinite)
const copy = p => [...p]

// Rendering derivatives only. Never persist these offsets, use them for takeoff,
// or infer electrical junctions/circuits from visual contact.
export function wiringRuns(segments, ownerId, style = () => '') {
  const runs = []
  segments.forEach((segment, index) => {
    if (!finite(segment.start) || !finite(segment.end) || same(segment.start, segment.end)) return
    const key = style(segment), previous = runs.at(-1)
    if (previous && previous.style === key && same(previous.points.at(-1), segment.start)) {
      previous.points.push(copy(segment.end)); previous.segmentIndices.push(index)
    } else runs.push({ id: `${ownerId}:${index}`, ownerId, style: key, segment,
      segmentIndices: [index], points: [copy(segment.start), copy(segment.end)] })
  })
  return runs
}

function parameter(point, a, b) {
  const delta = b.map((v, i) => v - a[i]), length2 = delta.reduce((s, v) => s + v*v, 0)
  if (length2 < EPS*EPS) return null
  const t = delta.reduce((s, v, i) => s + v*(point[i]-a[i]), 0)/length2
  return t >= -EPS && t <= 1+EPS && Math.hypot(...delta.map((v, i) => a[i]+t*v-point[i])) <= EPS
    ? Math.max(0, Math.min(1, t)) : null
}

function overlaps(a, b, radius) {
  if (Math.abs(a.start[1]-a.end[1]) > EPS || Math.abs(b.start[1]-b.end[1]) > EPS
    || Math.abs(a.start[1]-b.start[1]) > EPS) return false
  const axis = new Vector3(...a.end).sub(new Vector3(...a.start)), length = axis.length()
  if (length < EPS) return false
  axis.divideScalar(length)
  const from = p => new Vector3(...p).sub(new Vector3(...a.start))
  const start = from(b.start), end = from(b.end)
  const direction=end.clone().sub(start).normalize()
  if (Math.abs(direction.dot(axis))<.9999
    || start.clone().cross(axis).length()>radius*2.1 || end.clone().cross(axis).length()>radius*2.1) return false
  const projections = [start.dot(axis), end.dot(axis)].sort((x,y) => x-y)
  return Math.min(length, projections[1])-Math.max(0, projections[0]) > EPS
}

export function displayWiringRuns(runs, radius) {
  const result = runs.map(run => ({ ...run, sourcePoints: run.points.map(copy), points: run.points.map(copy), anchors: [], laneOffset: 0 }))
  const edges = result.flatMap((run, index) => run.points.slice(1).map((end, i) => ({
    run: index, start: run.points[i], end, eligible: run.spread !== false })))
  // Bound pairwise work on unusually dense pages; exact rendering is the fallback.
  if (result.length > 512 || edges.length > 1024) return result.map(run => ({ ...run, anchors: run.points }))
  const graph = result.map(() => new Set())
  for (let i=0; i<edges.length; i++) for (let j=i+1; j<edges.length; j++) {
    const a=edges[i], b=edges[j]
    if (a.run !== b.run && a.eligible && b.eligible
      && result[a.run].ownerId !== result[b.run].ownerId && overlaps(a,b,radius)) {
      graph[a.run].add(b.run); graph[b.run].add(a.run)
    }
  }
  const visited = new Set()
  result.forEach((_, index) => {
    if (visited.has(index) || !graph[index].size) return
    const component = [], queue = [index]
    while (queue.length) {
      const current = queue.pop()
      if (visited.has(current)) continue
      visited.add(current); component.push(current); queue.push(...graph[current])
    }
    component.sort((a,b) => String(result[a].id).localeCompare(String(result[b].id)))
    const spacing = Math.min(radius*2.6, radius*24/Math.max(1,component.length-1))
    component.forEach((i, rank) => { result[i].laneOffset = (rank-(component.length-1)/2)*spacing })
  })
  const contacts = result.flatMap((run,index) => run.points.map(point => ({point,run:index})))
  return result.map((run, index) => {
    const anchors = [...(run.connectionAnchors || []),run.points[0], run.points.at(-1)]
    const foreign = contacts.filter(c => c.run !== index)
    const points = []
    const append = p => { if (!points.length || !same(points.at(-1),p)) points.push(copy(p)) }
    run.points.slice(1).forEach((end, i) => {
      const start = run.points[i], split = [{t:0,point:start},{t:1,point:end}]
      for (const contact of foreign) {
        const t = parameter(contact.point,start,end)
        if (t != null) { anchors.push(contact.point); split.push({t,point:contact.point}) }
      }
      if (Math.abs(start[1]-end[1]) > EPS) anchors.push(start,end)
      split.sort((a,b) => a.t-b.t)
      const unique = split.filter((p,j) => !j || Math.abs(p.t-split[j-1].t)>EPS)
      unique.slice(1).forEach((next,j) => {
        const a=unique[j].point, b=next.point, delta=b.map((v,k)=>v-a[k]), length=Math.hypot(...delta)
        const horizontal=Math.abs(delta[1])<=EPS
        if (!run.laneOffset || !horizontal || length < radius*4) { append(a); append(b); return }
        // Terminals and observed branch contacts remain EXACT. A short taper
        // fans the display lane in/out; it is not a new stored elevation.
        const pinned = p => anchors.some(anchor => same(p,anchor))
        const lift = p => [p[0],p[1]+run.laneOffset,p[2]]
        const taper=Math.min(length*.22,Math.max(radius*6,Math.abs(run.laneOffset)*2))
        append(pinned(a) ? a : lift(a))
        if (pinned(a)) append(lift(a.map((v,k)=>v+delta[k]*taper/length)))
        if (pinned(b)) append(lift(b.map((v,k)=>v-delta[k]*taper/length)))
        append(pinned(b) ? b : lift(b))
      })
    })
    return {...run,points,anchors:anchors.map(copy)}
  })
}

export function roundedWiringCurve(points, radius, anchors = []) {
  if (!points.every(finite) || !Number.isFinite(radius) || radius<=0) throw new Error('Invalid display wiring geometry.')
  const clean=points.filter((p,i)=>!i || !same(p,points[i-1])).map(p=>new Vector3(...p))
  if (clean.length<2) return null
  const curve=new CurvePath()
  let previous=clean[0]
  const line = end => { if (previous.distanceTo(end)>EPS) curve.add(new LineCurve3(previous.clone(),end.clone())); previous=end }
  for (let i=1;i<clean.length-1;i++) {
    const corner=clean[i], before=clean[i-1], after=clean[i+1]
    const incoming=corner.clone().sub(before), outgoing=after.clone().sub(corner)
    const inLength=incoming.length(), outLength=outgoing.length()
    incoming.normalize(); outgoing.normalize()
    const dot=incoming.dot(outgoing)
    if (dot > .9999 || dot < -.95 || anchors.some(p=>same(p,corner.toArray()))) { line(corner); continue }
    const trim=Math.min(radius*3,inLength*.2,outLength*.2)
    const enter=corner.clone().addScaledVector(incoming,-trim), exit=corner.clone().addScaledVector(outgoing,trim)
    line(enter); curve.add(new QuadraticBezierCurve3(enter,corner.clone(),exit)); previous=exit
  }
  line(clean.at(-1))
  return curve.curves.length ? curve : null
}
