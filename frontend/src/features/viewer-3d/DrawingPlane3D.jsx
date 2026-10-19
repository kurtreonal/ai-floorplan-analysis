import { useEffect, useMemo } from 'react'
import { useThree } from '@react-three/fiber'
import { DoubleSide, Vector3 } from 'three'
import { sourcePointOnPlane } from './workPlaneDrawing.js'
import { deviceConnector, devicePlacement } from './devicePlacement.js'
import { WiringTargetMarker3D } from './WiringTargetMarker3D.jsx'

export function DrawingPlane3D({scene,drawing,tool}) {
  const {camera,pointer,size,get,setEvents}=useThree()
  useEffect(()=>{
    const previous=get().events.filter
    // Drawing owns clicks on the explicit plane, including clicks visually
    // over a device. Existing device handlers cannot steal them into a drag.
    setEvents({filter:items=>items.filter(hit=>hit.object.name==='drawing-work-plane-hit')})
    return()=>setEvents({filter:previous})
  },[get,setEvents])
  const points=useMemo(()=>[...drawing.vertices.map(v=>v.point),...(drawing.hover?[drawing.hover.point]:[])],[drawing.vertices,drawing.hover])
  const positions=useMemo(()=>new Float32Array(points.flatMap(p=>[p.x*scene.sourceScale,drawing.config.sceneElevation,p.y*scene.sourceScale])),[points,scene.sourceScale,drawing.config.sceneElevation])
  function point(event,commit) {
    event.stopPropagation()
    if(commit&&(event.button!==0||event.delta>4))return
    const raw=sourcePointOnPlane(event.ray,drawing.config.sceneElevation,scene)
    if(!raw)return
    const distance=position=>{
      const projected=new Vector3(...position).project(camera)
      return projected.z < -1 || projected.z > 1 ? Infinity : Math.hypot((projected.x-pointer.x)*size.width/2,(projected.y-pointer.y)*size.height/2)
    }
    const sourcePosition=p=>[p.x*scene.sourceScale,drawing.config.sceneElevation,p.y*scene.sourceScale]
    const origin=new Vector3(...sourcePosition(raw)).project(camera)
    const scales=[{x:raw.x+1,y:raw.y},{x:raw.x,y:raw.y+1}].map(p=>{
      const projected=new Vector3(...sourcePosition(p)).project(camera)
      return Math.hypot((projected.x-origin.x)*size.width/2,(projected.y-origin.y)*size.height/2)
    })
    drawing.pointer(raw,{shift:event.shiftKey,screenScale:Math.max(...scales),pathDistance:p=>distance(sourcePosition(p)),deviceDistance:symbol=>{
      const rendered=scene.symbols.find(s=>s.id===symbol.id)
      return rendered?distance(deviceConnector(devicePlacement(rendered,scene,rendered.presentation?.family||'unknown'))):Infinity
    }},commit)
  }
  return <group name="explicit-drawing-work-plane">
    <mesh name="drawing-work-plane-hit" position={[scene.width/2,drawing.config.sceneElevation,scene.depth/2]} rotation={[-Math.PI/2,0,0]}
      renderOrder={20} onPointerMove={event=>point(event,false)} onClick={event=>point(event,true)}>
      <planeGeometry args={[scene.width,scene.depth]} /><meshBasicMaterial color="#ff7a45" side={DoubleSide} transparent opacity={.035} depthWrite={false} />
    </mesh>
    {points.length>1&&<line renderOrder={21} raycast={()=>null}>
      <bufferGeometry><bufferAttribute attach="attributes-position" args={[positions,3]} /></bufferGeometry>
      <lineBasicMaterial color={tool==='wire'?'#ff7a45':'#172331'} depthTest={false} />
    </line>}
    {drawing.hover?.snapped&&<WiringTargetMarker3D position={[drawing.hover.point.x*scene.sourceScale,drawing.config.sceneElevation,drawing.hover.point.y*scene.sourceScale]} />}
  </group>
}
