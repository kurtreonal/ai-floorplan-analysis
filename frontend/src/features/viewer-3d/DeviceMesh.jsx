import { useEffect, useRef, useState } from 'react'
import { useThree } from '@react-three/fiber'
import { deviceFamily } from '../detection-review/devicePresentation.js'
import { startDeviceDrag, deviceDragPosition } from './deviceDrag.js'
import { devicePlacement } from './devicePlacement.js'

function BoxPart({ size, position = [0, 0, 0], color }) {
  return <mesh position={position}><boxGeometry args={size} /><meshStandardMaterial color={color} roughness={0.65} /></mesh>
}

function RoundPart({ radius, height, y, color }) {
  return <mesh position={[0, y, 0]}><cylinderGeometry args={[radius, radius, height, 16]} /><meshStandardMaterial color={color} roughness={0.65} /></mesh>
}

// Physical-size preview defaults. Authoritative XY anchors remain in the shared draft.
export function DeviceMesh({ symbol, scene, selected, onSelect, onMove, onDraggingChange }) {
  const { invalidate } = useThree()
  const groupRef = useRef(null)
  const drag = useRef(null)
  const [hovered, setHovered] = useState(false)
  useEffect(() => () => { if (drag.current) onDraggingChange?.(false) }, [onDraggingChange])
  const family = symbol.presentation?.family || deviceFamily(symbol.classification?.name)
  const name = symbol.presentation?.label || symbol.classification?.name || 'Unclassified device'
  const placement = devicePlacement(symbol, scene, family)
  const finishDrag = (event, commit) => {
    const current = drag.current
    if (!current || current.pointerId !== event.pointerId) return
    drag.current = null
    event.stopPropagation()
    event.target.releasePointerCapture?.(event.pointerId)
    onDraggingChange?.(false)
    const position = groupRef.current?.position
    if (commit && current.moved && position) onMove?.(symbol.id, {
      x: position.x - placement.anchorOffset[0], y: position.z - placement.anchorOffset[1],
    })
    groupRef.current?.position.set(...placement.position)
    invalidate()
  }
  return <group ref={groupRef} name={`${symbol.id}: ${name}`} position={placement.position}
    onPointerOver={(event) => { event.stopPropagation(); setHovered(true) }}
    onPointerOut={() => setHovered(false)}
    onClick={(event) => { event.stopPropagation(); onSelect?.(symbol.id) }}
    onPointerDown={(event) => {
      if (event.button !== 0) return
      event.stopPropagation()
      onSelect?.(symbol.id)
      if (!onMove) return
      const start = startDeviceDrag(event.ray, placement.position)
      if (!start) return
      drag.current = { ...start, pointerId: event.pointerId, moved: false }
      event.target.setPointerCapture?.(event.pointerId)
      onDraggingChange?.(true)
    }}
    onPointerMove={(event) => {
      const current = drag.current
      if (!current || current.pointerId !== event.pointerId) return
      event.stopPropagation()
      const point = deviceDragPosition(event.ray, current, scene)
      if (!point) return
      const { x, z } = point
      current.moved ||= Math.hypot(x - placement.position[0], z - placement.position[2]) > 0.001
      groupRef.current?.position.set(x, placement.position[1], z)
      invalidate()
    }} onPointerUp={(event) => finishDrag(event, true)} onPointerCancel={(event) => finishDrag(event, false)}
    onLostPointerCapture={(event) => finishDrag(event, false)}>
    <group scale={placement.size} rotation={[0, placement.rotation, 0]}>
      {family === 'troffer' || family === 'linear-light' ? <>
        <BoxPart size={[1, 1, 1]} color="#8397a1" />
        <BoxPart size={[0.92, 0.12, 0.94]} position={[0, -0.47, 0]} color="#fffbed" />
        {[-0.3, 0, 0.3].map((z) => <BoxPart key={z} size={[0.94, 0.08, 0.02]} position={[0, -0.51, z]} color="#aeb8b9" />)}
      </> : family === 'round-light' || family === 'detector' || family === 'alarm' ? <>
        <group rotation={family === 'alarm' ? [Math.PI / 2, 0, 0] : [0, 0, 0]}>
          <RoundPart radius={0.5} height={0.9} y={0} color={family === 'alarm' ? '#c94e28' : '#e5e4de'} />
          <RoundPart radius={0.42} height={0.1} y={-0.46} color={family === 'alarm' ? '#ff6a3d' : '#fffbed'} />
          {family === 'detector' && <RoundPart radius={0.1} height={0.1} y={-0.48} color="#41586b" />}
        </group>
      </> : family === 'panel' ? <>
        <BoxPart size={[1, 1, 1]} color="#41586b" />
        <BoxPart size={[0.9, 0.92, 0.04]} position={[0, 0, 0.51]} color="#a8b0b0" />
        <BoxPart size={[0.03, 0.2, 0.07]} position={[0.32, 0, 0.54]} color="#151515" />
      </> : family === 'outlet' || family === 'switch' || family === 'pull-station' ? <>
        <BoxPart size={[1, 1, 1]} color={family === 'pull-station' ? '#c94e28' : '#fdfcf8'} />
        {family === 'outlet' ? [-0.22, 0.22].map((y) => <group key={y} position={[0, y, 0.52]}>
          <BoxPart size={[0.08, 0.14, 0.04]} position={[-0.15, 0, 0]} color="#151515" />
          <BoxPart size={[0.08, 0.14, 0.04]} position={[0.15, 0, 0]} color="#151515" />
        </group>) : <BoxPart size={[0.55, 0.65, 0.08]} position={[0, 0, 0.53]} color={family === 'pull-station' ? '#fdfcf8' : '#41586b'} />}
      </> : family === 'annotation' ? <mesh rotation={[-Math.PI / 2, 0, 0]}><coneGeometry args={[0.5, 1, 3]} /><meshStandardMaterial color="#c94e28" /></mesh>
        : <mesh><octahedronGeometry args={[0.5]} /><meshStandardMaterial color="#c94e28" wireframe /></mesh>}
      {(selected || hovered) && <mesh><boxGeometry args={[1.08, 1.08, 1.08]} /><meshBasicMaterial color={selected ? '#ff6a3d' : '#4f7c93'} wireframe /></mesh>}
    </group>
  </group>
}
