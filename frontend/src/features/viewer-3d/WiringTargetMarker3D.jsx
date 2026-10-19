import { useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { wireHandleRadius } from './wireHandleProjection.js'

export function WiringTargetMarker3D({position}) {
  const ref=useRef(null)
  const {camera,size}=useThree()
  useFrame(()=>ref.current?.scale.setScalar(wireHandleRadius(position,camera,size.height,10)))
  return <mesh ref={ref} name="chosen-wire-terminal-3d" position={position}
    scale={wireHandleRadius(position,camera,size.height,10)} renderOrder={12} raycast={()=>null}>
    <sphereGeometry args={[1,16,12]} /><meshBasicMaterial color="#13816c" wireframe depthTest={false} />
  </mesh>
}
