import { useEffect, useMemo } from 'react'
import { useThree } from '@react-three/fiber'
import { TubeGeometry } from 'three'
import { Line2 } from 'three/addons/lines/Line2.js'
import { LineGeometry } from 'three/addons/lines/LineGeometry.js'
import { LineMaterial } from 'three/addons/lines/LineMaterial.js'
import { wiringRenderPath } from './wiringPresentation.js'

export function WiringTube3D({ run, radius, color, onClick, xray = false,opacity=1,proposal=false }) {
  const { size } = useThree()
  const pickable=Boolean(onClick)
  const path = useMemo(() => wiringRenderPath(run.points,radius,run.anchors),[run,radius])
  const geometry = useMemo(() => {
    return path && !proposal ? new TubeGeometry(path,path.points.length-1,radius,12,false) : null
  },[path,radius,proposal])
  const pickGeometry = useMemo(() => {
    if (!pickable) return null
    return path ? new TubeGeometry(path,path.points.length-1,radius*2.2,6,false) : null
  },[path,radius,pickable])
  useEffect(()=>()=>geometry?.dispose(),[geometry])
  useEffect(()=>()=>pickGeometry?.dispose(),[pickGeometry])
  // Pixel-sized inspection stroke follows the same display curve as the tube.
  // It is not engineering geometry and never feeds measurement or purchase sizing.
  const inspectionLine = useMemo(() => {
    if (!xray && !proposal) return null
    if (!path) return null
    const geometry = new LineGeometry().setPositions(path.points.flatMap(point=>point.toArray()))
    const material = new LineMaterial({color,linewidth:1.7,depthTest:!xray,depthWrite:false,transparent:true,
      opacity:opacity*(proposal ? .65 : 1),dashed:proposal,dashSize:radius*14,gapSize:radius*9})
    const line = new Line2(geometry,material)
    line.computeLineDistances()
    line.renderOrder = 12
    line.raycast = () => null
    return line
  },[xray,path,color,opacity,proposal,radius])
  useEffect(()=>{
    inspectionLine?.material.resolution.set(size.width,size.height)
  },[inspectionLine,size.width,size.height])
  useEffect(()=>()=>{
    inspectionLine?.geometry.dispose()
    inspectionLine?.material.dispose()
  },[inspectionLine])
  if (!path) return null
  // Physical tubes occlude each other normally. Only the thin inspection
  // stroke sees through architecture, avoiding stacked translucent cylinders.
  const inspection={depthTest:true,depthWrite:opacity>=1}
  return <group name="wiring-display-run" onClick={onClick}
    userData={{ displayOnly:true,laneOffset:run.laneOffset || 0,proposal }}>
    {geometry && <mesh name="wiring-route-tube" geometry={geometry} renderOrder={xray ? 10 : 0}>
      <meshStandardMaterial color={color} roughness={.3} metalness={.15} transparent={opacity<1} opacity={opacity} {...inspection} />
    </mesh>}
    {pickGeometry && <mesh name="pick-wiring-run" geometry={pickGeometry}>
      <meshBasicMaterial transparent opacity={0} depthWrite={false} />
    </mesh>}
    {inspectionLine && <primitive name="wiring-inspection-stroke" object={inspectionLine} dispose={null}/>}
    {!proposal && [run.points[0],run.points.at(-1)].map((position,i)=><mesh key={i} name="wire-end-cap" position={position} renderOrder={xray ? 10 : 0}>
      <sphereGeometry args={[radius,12,8]} />
      <meshStandardMaterial color={color} roughness={.3} metalness={.15} transparent={opacity<1} opacity={opacity} {...inspection} />
    </mesh>)}
  </group>
}
