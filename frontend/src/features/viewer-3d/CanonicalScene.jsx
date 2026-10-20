import { useMemo } from 'react'
import { DoubleSide, Shape } from 'three'
import { canonicalRoomShapePoints } from './canonicalScene.js'
import { DeviceMesh } from './DeviceMesh.jsx'
import { roofPreview } from './roofPreview.js'
import { ROUTE_DISPLAY_RADIUS } from '../routing/routeMesh.js'
import { wiringDesign } from '../routing/wiringDesign.js'
import { displayWiringRuns, wiringRuns } from '../routing/wiringPresentation.js'
import { WiringTube3D } from '../routing/WiringTube3D.jsx'
import {JoinedWallMesh} from './JoinedWallMesh.jsx'
import {WALL_APPEARANCE} from '../detection-review/wallAppearance.js'

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
    <meshStandardMaterial color={roof ? '#e2e1dc' : '#e6e4dd'} side={DoubleSide} polygonOffset polygonOffsetFactor={-1} />
  </mesh>
}

export function CanonicalScene({ scene, showRoof = false, selectedSymbolId, selectedWallId, onSelectSymbol, onSelectWall, onMoveSymbol, onDraggingChange }) {
  const runs=useMemo(()=>{
    const routes=new Map()
    for(const segment of scene.routeSegments ?? []) {
      if(!routes.has(segment.routeId)) routes.set(segment.routeId,[])
      routes.get(segment.routeId).push(segment)
    }
    return displayWiringRuns([...routes].flatMap(([id,segments])=>wiringRuns(segments,id,s=>wiringDesign(s).color)
      .map(run=>({...run,connectionAnchors:segments.flatMap(s => s.connectionAnchors || []),
        spread:run.segment.installationMethod==='concealed_in_ceiling'}))),ROUTE_DISPLAY_RADIUS)
  },[scene.routeSegments])
  return <group>
    <mesh position={[scene.width / 2, scene.elevation, scene.depth / 2]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[scene.width, scene.depth]} />
      <meshStandardMaterial color="#e9e5dc" side={DoubleSide} />
    </mesh>
    {scene.rooms.map((room) => <RoomSurface key={room.id} room={room} elevation={scene.elevation} />)}
    {showRoof && roofPreview(scene).map((room) => <RoomSurface key={`roof-${room.id}`} room={room} elevation={room.elevation} roof />)}
    {scene.walls.map((wall) => wall.footprints ? <JoinedWallMesh key={wall.id} wall={wall} selected={wall.id === selectedWallId}
      onClick={onSelectWall ? event=>{event.stopPropagation();onSelectWall(wall.id,event)} : undefined} /> : <mesh key={wall.id} position={wall.position} rotation={wall.rotation}
      onClick={onSelectWall ? event=>{event.stopPropagation();onSelectWall(wall.id,event)} : undefined}>
      <boxGeometry args={wall.size} />
      <meshStandardMaterial color={wall.id === selectedWallId ? '#ff7a45' : WALL_APPEARANCE.normal} roughness={.82} />
    </mesh>)}
    {runs.map((run) => {
      const segment=run.segment
      const color = wiringDesign(segment).color
      return <group name="canonical-route" key={run.id}
        userData={{ routeId: segment.routeId, provenance: segment.provenance,
          installationMethod: segment.installationMethod, elevationState: segment.elevationState,
          displayRadiusOnly: true }}>
        <WiringTube3D run={run} radius={ROUTE_DISPLAY_RADIUS} color={color} />
      </group>
    })}
    {scene.symbols.map((symbol) => <DeviceMesh key={symbol.id} symbol={symbol} scene={scene}
      selected={selectedSymbolId === symbol.id} onSelect={onSelectSymbol} onMove={onMoveSymbol} onDraggingChange={onDraggingChange} />)}
  </group>
}
