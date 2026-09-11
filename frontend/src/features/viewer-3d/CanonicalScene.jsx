import { useMemo } from 'react'
import { DoubleSide, Shape } from 'three'

function RoomSurface({ room, elevation }) {
  const shape = useMemo(() => {
    const result = new Shape()
    room.boundary.forEach((point, index) => {
      if (index === 0) result.moveTo(point.x, -point.y)
      else result.lineTo(point.x, -point.y)
    })
    result.closePath()
    return result
  }, [room])
  return <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, elevation, 0]}>
    <shapeGeometry args={[shape]} />
    <meshStandardMaterial color="#d3dfce" side={DoubleSide} polygonOffset polygonOffsetFactor={-1} />
  </mesh>
}

export function CanonicalScene({ scene }) {
  return <group>
    <mesh position={[scene.width / 2, scene.elevation, scene.depth / 2]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[scene.width, scene.depth]} />
      <meshStandardMaterial color="#e9e5dc" side={DoubleSide} />
    </mesh>
    {scene.rooms.map((room) => <RoomSurface key={room.id} room={room} elevation={scene.elevation} />)}
    {scene.walls.map((wall) => <mesh key={wall.id} position={wall.position} rotation={wall.rotation}>
      <boxGeometry args={wall.size} />
      <meshStandardMaterial color="#8397a1" />
    </mesh>)}
    {scene.symbols.map((symbol) => <mesh key={symbol.id} position={symbol.position}>
      <sphereGeometry args={[0.09, 12, 8]} />
      <meshBasicMaterial color="#ff652f" depthTest={false} />
    </mesh>)}
  </group>
}
