import { useEffect, useMemo } from 'react'
import { TubeGeometry } from 'three'
import { roundedWiringCurve } from './wiringPresentation.js'

export function WiringTube3D({ run, radius, color, onClick, xray = false }) {
  const pickable=Boolean(onClick)
  const geometry = useMemo(() => {
    const curve=roundedWiringCurve(run.points,radius,run.anchors)
    return curve ? new TubeGeometry(curve,Math.min(512,Math.max(12,curve.curves.length*8)),radius,12,false) : null
  },[run,radius])
  const pickGeometry = useMemo(() => {
    if (!pickable) return null
    const curve=roundedWiringCurve(run.points,radius,run.anchors)
    return curve ? new TubeGeometry(curve,Math.min(256,Math.max(12,curve.curves.length*6)),radius*2.2,6,false) : null
  },[run,radius,pickable])
  useEffect(()=>()=>geometry?.dispose(),[geometry])
  useEffect(()=>()=>pickGeometry?.dispose(),[pickGeometry])
  if (!geometry) return null
  const inspection=xray ? {depthTest:false,depthWrite:false} : {}
  return <group name="wiring-display-run" onClick={onClick}
    onPointerDown={onClick ? event=>{if(event.button===0) onClick(event)} : undefined}
    userData={{ displayOnly:true,laneOffset:run.laneOffset || 0 }}>
    <mesh name="wiring-route-tube" geometry={geometry} renderOrder={xray ? 10 : 0}>
      <meshStandardMaterial color={color} roughness={.3} metalness={.15} {...inspection} />
    </mesh>
    {pickGeometry && <mesh name="pick-wiring-run" geometry={pickGeometry}>
      <meshBasicMaterial transparent opacity={0} depthWrite={false} />
    </mesh>}
    {[run.points[0],run.points.at(-1)].map((position,i)=><mesh key={i} name="wire-end-cap" position={position} renderOrder={xray ? 10 : 0}>
      <sphereGeometry args={[radius,12,8]} />
      <meshStandardMaterial color={color} roughness={.3} metalness={.15} {...inspection} />
    </mesh>)}
  </group>
}
