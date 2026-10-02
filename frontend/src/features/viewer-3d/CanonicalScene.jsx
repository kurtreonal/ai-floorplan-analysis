import { useMemo } from 'react'
import { DoubleSide, Shape } from 'three'
import { canonicalRoomShapePoints } from './canonicalScene.js'
import { DeviceMesh } from './DeviceMesh.jsx'
import { roofPreview } from './roofPreview.js'

function RoomSurface({ room, elevation, roof = false }) {
  const shape = useMemo(() => {
    const result = new Shape()
    canonicalRoomShapePoints(room.boundary).forEach(([x, y], index) => {
      if (index === 0) result.moveTo(x, y)
      else result.lineTo(x, y)
    })
    result.closePath()
    return result
  }, [room])
  return <mesh name={roof ? 'roof-preview' : 'room-floor'} rotation={[-Math.PI / 2, 0, 0]} position={[0, elevation, 0]}>
    <shapeGeometry args={[shape]} />
    <meshStandardMaterial color={roof ? '#e2e1dc' : '#d3dfce'} side={DoubleSide} polygonOffset polygonOffsetFactor={-1} />
  </mesh>
}

export function CanonicalScene({ scene, showRoof = false, selectedSymbolId, onSelectSymbol, onMoveSymbol, onDraggingChange }) {
  return <group>
    <mesh position={[scene.width / 2, scene.elevation, scene.depth / 2]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[scene.width, scene.depth]} />
      <meshStandardMaterial color="#e9e5dc" side={DoubleSide} />
    </mesh>
    {scene.rooms.map((room) => <RoomSurface key={room.id} room={room} elevation={scene.elevation} />)}
    {showRoof && roofPreview(scene).map((room) => <RoomSurface key={`roof-${room.id}`} room={room} elevation={room.elevation} roof />)}
    {scene.walls.map((wall) => <mesh key={wall.id} position={wall.position} rotation={wall.rotation}>
      <boxGeometry args={wall.size} />
      <meshStandardMaterial color="#8397a1" />
    </mesh>)}
    {scene.symbols.map((symbol) => <DeviceMesh key={symbol.id} symbol={symbol} scene={scene}
      selected={selectedSymbolId === symbol.id} onSelect={onSelectSymbol} onMove={onMoveSymbol} onDraggingChange={onDraggingChange} />)}
  </group>
}
