import {useMemo,useEffect} from 'react'
import {joinedWallGeometry} from './wallGeometry.js'
import {StudioWallMaterial} from './StudioWallMaterial.jsx'

export function JoinedWallMesh({wall,selected=false,onClick,wallMode='full',bounds}) {
  const geometry=useMemo(()=>joinedWallGeometry(wall),[wall])
  useEffect(()=>()=>geometry.dispose(),[geometry])
  return <mesh castShadow receiveShadow name="joined-wall" userData={{wallId:wall.id}} geometry={geometry} position={[0,wall.elevation,0]} onClick={onClick}>
    <StudioWallMaterial mode={wallMode} bounds={bounds} selected={selected} wall={wall} />
  </mesh>
}
