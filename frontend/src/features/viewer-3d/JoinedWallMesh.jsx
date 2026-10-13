import {useMemo,useEffect} from 'react'
import {joinedWallGeometry} from './wallGeometry.js'
import {WALL_APPEARANCE} from '../detection-review/wallAppearance.js'

export function JoinedWallMesh({wall}) {
  const geometry=useMemo(()=>joinedWallGeometry(wall),[wall])
  useEffect(()=>()=>geometry.dispose(),[geometry])
  return <mesh name="joined-wall" userData={{wallId:wall.id}} geometry={geometry} position={[0,wall.elevation,0]}>
    <meshStandardMaterial color={WALL_APPEARANCE.normal} roughness={.82} />
  </mesh>
}
