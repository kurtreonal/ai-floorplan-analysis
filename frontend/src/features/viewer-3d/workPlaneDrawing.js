import { findWireEndpointTargets } from '../detection-review/wirePathSnap.js'
import { compatibleWires, activeWire } from '../detection-review/connectedWiring.js'
import { findSnapPoint } from '../detection-review/wallEditorUtils.js'

const number = value => value === '' || value == null ? NaN : Number(value)

export function drawingWorkPlane(tool, settings, context, scene) {
  const ppm=context?.pixels_per_meter, floor=context?.floor_elevation_meters
  if (!Number.isFinite(ppm) || ppm<=0 || !Number.isFinite(floor)) throw new Error('Review the plan scale and floor elevation before drawing in 3D.')
  if (!scene || !Number.isFinite(scene.unitsPerMeter) || scene.unitsPerMeter<=0
    || Math.abs(scene.sourceScale*ppm-scene.unitsPerMeter)>1e-8) throw new Error('The 3D view does not match the calibrated source plane.')
  const elevation=tool==='draw' ? floor : number(settings.elevation)
  if (!Number.isFinite(elevation) || elevation < -1000 || elevation > 10000) throw new Error('Enter a service elevation in metres from the project datum.')
  const circuitId=settings.circuit?.trim() || null
  if(circuitId&&circuitId.length>80)throw new Error('Circuit identifiers must be at most 80 characters.')
  const config={elevation,sceneElevation:(elevation-floor)*scene.unitsPerMeter,ppm,axis:settings.axis || 'none',circuitId}
  if (tool==='draw') {
    const thickness=number(settings.thickness), height=number(settings.height), length=settings.length==='' ? null : number(settings.length)
    if (![thickness,height].every(n=>Number.isFinite(n)&&n>0&&n<=1000) || thickness*ppm>1000) throw new Error('Enter wall thickness and height within the source geometry limits.')
    if (length!==null && (!Number.isFinite(length)||length<=0)) throw new Error('Enter a positive wall length or leave it blank.')
    Object.assign(config,{thickness,height,length})
  }
  return config
}

// Intersect a real camera ray with the selected horizontal plane, not the
// perspective screen's X/Y. Parallel, backwards and out-of-page hits reject.
export function sourcePointOnPlane(ray, elevation, scene) {
  if (!ray || !Number.isFinite(elevation) || !Number.isFinite(scene?.sourceScale) || scene.sourceScale<=0) return null
  const {origin:o,direction:d}=ray
  if (![o.x,o.y,o.z,d.x,d.y,d.z].every(Number.isFinite) || Math.abs(d.y)<1e-8) return null
  const t=(elevation-o.y)/d.y
  if (t<0) return null
  const x=o.x+t*d.x,z=o.z+t*d.z
  if (x<0 || z<0 || x>scene.width || z>scene.depth) return null
  return {x:x/scene.sourceScale,y:z/scene.sourceScale}
}

export function spatialDrawingTarget(raw,{tool,vertices,draft,presentations,config,method,snapping=true,shift=false,screenScale=1,deviceDistance,pathDistance}) {
  const anchor=vertices.at(-1)?.point
  const axis=anchor&&shift&&config.axis==='none' ? Math.abs(raw.x-anchor.x)>=Math.abs(raw.y-anchor.y)?'x':'y' : config.axis
  let point=anchor ? axis==='x' ? {x:raw.x,y:anchor.y} : axis==='y' ? {x:anchor.x,y:raw.y} : raw : raw
  if (tool==='draw') {
    const snap=snapping ? findSnapPoint(point,draft.walls,{threshold:12/Math.max(screenScale,1e-8)}) : {...point,snapped:false}
    if (anchor && config.length!==null) {
      const direction={x:snap.x-anchor.x,y:snap.y-anchor.y}, distance=Math.hypot(direction.x,direction.y)
      if (!distance) return {point:anchor}
      point={x:anchor.x+direction.x/distance*config.length*config.ppm,y:anchor.y+direction.y/distance*config.length*config.ppm}
      // A nearby corner never overrides an explicitly entered physical length.
      return {point}
    }
    point={x:snap.x,y:snap.y}
    if(anchor && ((axis==='x'&&point.y!==anchor.y)||(axis==='y'&&point.x!==anchor.x)))return {point:axis==='x'?{x:raw.x,y:anchor.y}:{x:anchor.x,y:raw.y}}
    return {point,snapped:snap.snapped}
  }
  if (!snapping) return {point}
  const attributes={circuit_id:config.circuitId??null,elevation_meters:config.elevation,installation_method:method}
  const probe={...attributes,id:'drawing-probe',points:[point,anchor || {x:-1,y:-1}]}
  const choices=findWireEndpointTargets(point,probe.id,0,{...draft,wirings:[...draft.wirings,probe]},presentations,12,
    deviceDistance || (s=>Math.hypot(s.center.x-point.x,s.center.y-point.y)*screenScale),
    pathDistance || (p=>Math.hypot(p.x-point.x,p.y-point.y)*screenScale))
    .filter(c=> !(anchor&&((axis==='x'&&c.point.y!==anchor.y)||(axis==='y'&&c.point.x!==anchor.x))))
    .filter(c=> c.kind!=='device' || !draft.wirings.filter(activeWire).some(w=>w.device_attachments?.some(a=>a.symbol_id===c.symbolId&&a.terminal_id===c.terminalId)&&!compatibleWires(w,probe)))
  if (choices.length!==1) return {point,choices}
  return {...drawingTargetVertex(choices[0]),choices}
}

export function drawingTargetVertex(target) {
  const point={...target.point}
  return {point,snapped:true,snap:{x:point.x,y:point.y,snapped:true,
    kind:target.kind==='device'?'device':'wire',id:target.symbolId || target.wireId,
    ...(target.terminalId?{terminalId:target.terminalId}:{})}}
}
