import { useEffect, useMemo, useRef, useState } from 'react'
import { useThree } from '@react-three/fiber'
import { deviceFamily } from '../detection-review/devicePresentation.js'
import { startDeviceDrag, deviceDragPosition } from './deviceDrag.js'
import { devicePlacement } from './devicePlacement.js'
import { DeviceBody } from './DeviceBody.jsx'
import { SELECTION_CLICK_PIXELS } from './selectionGesture.js'

// Physical-size preview defaults. Authoritative XY anchors remain in the shared draft.
export function DeviceMesh({ symbol, scene, selected, onSelect, onMove, onDraggingChange }) {
  const { invalidate } = useThree()
  const groupRef = useRef(null)
  const drag = useRef(null)
  const [hovered, setHovered] = useState(false)
  const family = symbol.presentation?.family || deviceFamily(symbol.classification?.name)
  const name = symbol.presentation?.label || symbol.classification?.name || 'Unclassified device'
  const placement = useMemo(()=>devicePlacement(symbol, scene, family),[symbol,scene,family])
  useEffect(()=>{
    const cancel = event => {
      if (event.type !== 'blur' && event.key !== 'Escape' || !drag.current) return
      const current = drag.current; drag.current = null
      if (current.target.hasPointerCapture?.(current.pointerId)) current.target.releasePointerCapture?.(current.pointerId)
      groupRef.current?.position.set(...placement.position)
      onDraggingChange?.(false); invalidate()
    }
    window.addEventListener('blur',cancel); window.addEventListener('keydown',cancel)
    return ()=>{cancel({type:'blur'});window.removeEventListener('blur',cancel);window.removeEventListener('keydown',cancel)}
  },[invalidate,onDraggingChange,placement])
  const finishDrag = (event, commit) => {
    const current = drag.current
    if (!current || current.pointerId !== event.pointerId) return
    drag.current = null
    event.stopPropagation()
    if (event.target.hasPointerCapture?.(event.pointerId)) event.target.releasePointerCapture?.(event.pointerId)
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
    onClick={(event) => { if (!onSelect) return; event.stopPropagation(); onSelect(symbol.id,event) }}
    onPointerDown={(event) => {
      if (event.button !== 0) return
      if (!onMove || !selected) return
      event.stopPropagation()
      const start = startDeviceDrag(event.ray, placement.position)
      if (!start) return
      drag.current = { ...start, pointerId: event.pointerId, moved: false, screen:{x:event.clientX,y:event.clientY},target:event.target }
      event.target.setPointerCapture?.(event.pointerId)
      onDraggingChange?.(true)
    }}
    onPointerMove={(event) => {
      const current = drag.current
      if (!current || current.pointerId !== event.pointerId) return
      event.stopPropagation()
      if (!current.moved && Math.hypot(event.clientX-current.screen.x,event.clientY-current.screen.y) <= SELECTION_CLICK_PIXELS) return
      const point = deviceDragPosition(event.ray, current, scene)
      if (!point) return
      const { x, z } = point
      current.moved ||= Math.hypot(x - placement.position[0], z - placement.position[2]) > 0.001
      groupRef.current?.position.set(x, placement.position[1], z)
      invalidate()
    }} onPointerUp={(event) => finishDrag(event, true)} onPointerCancel={(event) => finishDrag(event, false)}
    onLostPointerCapture={(event) => finishDrag(event, false)}>
    <group scale={placement.size} rotation={[0, placement.rotation, 0]}>
      <DeviceBody family={family} label={name} selected={selected} />
      {(selected || hovered) && <mesh><boxGeometry args={[1.08, 1.08, 1.08]} /><meshBasicMaterial color={selected ? '#ff6a3d' : '#4f7c93'} wireframe /></mesh>}
    </group>
  </group>
}
