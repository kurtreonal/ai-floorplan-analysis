import { useEffect, useMemo, useRef, useState } from 'react'
import { useThree } from '@react-three/fiber'
import { BoxGeometry, EdgesGeometry } from 'three'
import { deviceFamily } from '../detection-review/devicePresentation.js'
import { startDeviceDrag, deviceDragPosition, mountDraggedDevice } from './deviceDrag.js'
import { devicePlacement } from './devicePlacement.js'
import { StudioDeviceAsset } from './StudioDeviceAsset.jsx'
import { studioAsset } from './studioAssets.js'
import { SELECTION_CLICK_PIXELS } from './selectionGesture.js'

function DeviceOutline({selected}) {
  const geometry=useMemo(()=>{const box=new BoxGeometry(1.08,1.08,1.08);const edges=new EdgesGeometry(box);box.dispose();return edges},[])
  useEffect(()=>()=>geometry.dispose(),[geometry])
  return <lineSegments geometry={geometry} renderOrder={21}><lineBasicMaterial color={selected?'#ff6a3d':'#4f7c93'} depthTest={false} depthWrite={false}/></lineSegments>
}

// Physical-size preview defaults. Authoritative XY anchors remain in the shared draft.
export function DeviceMesh({ symbol, scene, selected, onSelect, onMove, onDraggingChange,product }) {
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
      x: current.mount?.anchorX ?? position.x - placement.anchorOffset[0], y: current.mount?.anchorZ ?? position.z - placement.anchorOffset[1],
      ...(placement.mount === 'wall' ? { mountingHeight: (position.y - scene.elevation) / (scene.unitsPerMeter ?? 1),
        mountingWallId: current.mount?.wallId || placement.mountedWallId } : {}),
    })
    groupRef.current?.position.set(...placement.position)
    invalidate()
  }
  return <group ref={groupRef} name={`${symbol.id}: ${name}`} position={placement.position} userData={{vedDeviceId:symbol.id}}
    onPointerOver={(event) => { event.stopPropagation(); setHovered(true) }}
    onPointerOut={() => setHovered(false)}
    onClick={(event) => { if (!onSelect) return; event.stopPropagation(); onSelect(symbol.id,event) }}
    onPointerDown={(event) => {
      if (event.button !== 0) return
      if (!onMove || !selected) return
      event.stopPropagation()
      const normal = placement.mount === 'wall' ? [Math.sin(placement.rotation), 0, Math.cos(placement.rotation)] : undefined
      const start = startDeviceDrag(event.ray, placement.position, normal)
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
      const mounted = mountDraggedDevice(point, placement, scene)
      const { x, y, z } = mounted
      current.mount = mounted
      current.moved ||= Math.hypot(x - placement.position[0], y - placement.position[1], z - placement.position[2]) > 0.001
      groupRef.current?.position.set(x, y, z)
      invalidate()
    }} onPointerUp={(event) => finishDrag(event, true)} onPointerCancel={(event) => finishDrag(event, false)}
    onLostPointerCapture={(event) => finishDrag(event, false)}>
    <group scale={placement.size} rotation={[0, placement.rotation, 0]}>
      {onSelect && <mesh name="device-pick-target"><boxGeometry args={[1.4,1.4,1.8]}/><meshBasicMaterial visible={false}/></mesh>}
      <StudioDeviceAsset asset={studioAsset(symbol,product)} family={family} label={name} selected={selected} />
      {(selected || hovered) && <DeviceOutline selected={selected}/>}
    </group>
  </group>
}
