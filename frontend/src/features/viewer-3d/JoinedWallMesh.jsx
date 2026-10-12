import {useMemo,useEffect} from 'react'
import {joinedWallGeometry} from './wallGeometry.js'

export function JoinedWallMesh({wall}) {
  const geometry=useMemo(()=>joinedWallGeometry(wall),[wall])
  useEffect(()=>()=>geometry.dispose(),[geometry])
  return <mesh name="joined-wall" userData={{wallId:wall.id}} geometry={geometry} position={[0,wall.elevation,0]}>
    <meshStandardMaterial color="#c4cbc9" roughness={.82} />
  </mesh>
}
