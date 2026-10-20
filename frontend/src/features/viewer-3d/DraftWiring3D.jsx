import { useEffect, useMemo, useRef, useState } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { Vector3 } from 'three'
import { ROUTE_DISPLAY_RADIUS } from '../routing/routeMesh.js'
import { displayWiringRuns, wiringRuns } from '../routing/wiringPresentation.js'
import { WiringTube3D } from '../routing/WiringTube3D.jsx'
import { startDeviceDrag, deviceDragPosition } from './deviceDrag.js'
import { wiringAppearance } from '../detection-review/wiringAppearance.js'
import { deviceConnector, devicePlacement } from './devicePlacement.js'
import { wireHandleRadius } from './wireHandleProjection.js'

export function WireHandle({ position, scene, onMove, onFindSnap, onChooseTarget, onDraggingChange }) {
  const ref = useRef(null), drag = useRef(null)
  const magnetRef = useRef(null)
  const { invalidate, camera, pointer, size } = useThree()
  const [snapPreview, setSnapPreview] = useState(null)
  useFrame(() => {
    if (ref.current) ref.current.scale.setScalar(wireHandleRadius(ref.current.position.toArray(),camera,size.height))
    if (magnetRef.current) magnetRef.current.scale.setScalar(wireHandleRadius(magnetRef.current.position.toArray(),camera,size.height,10))
  })
  useEffect(() => () => { if (drag.current) onDraggingChange?.(false) }, [onDraggingChange])
  useEffect(() => {
    function cancel(event) {
      if (event.type !== 'blur' && event.key !== 'Escape' || !drag.current) return
      const current = drag.current
      drag.current = null
      current.target.releasePointerCapture?.(current.pointerId)
      onDraggingChange?.(false)
      setSnapPreview(null)
      ref.current?.position.set(...position)
      invalidate()
    }
    window.addEventListener('keydown',cancel)
    window.addEventListener('blur',cancel)
    return () => {cancel({type:'blur'});window.removeEventListener('keydown',cancel);window.removeEventListener('blur',cancel)}
  }, [invalidate, onDraggingChange, position])
  function finish(event, commit) {
    const current = drag.current
    if (!current || current.pointerId !== event.pointerId) return
    drag.current = null; event.stopPropagation(); event.target.releasePointerCapture?.(event.pointerId)
    onDraggingChange?.(false)
    setSnapPreview(null)
    if (commit && current.moved && ref.current) {
      const point = { x: ref.current.position.x, y: ref.current.position.z }
      if (current.choices?.length > 1) onChooseTarget?.(current.choices)
      else if (current.snap) onMove(point,current.snap)
      else onMove(point)
    }
    ref.current?.position.set(...position); invalidate()
  }
  return <group><mesh ref={ref} position={position} scale={wireHandleRadius(position,camera,size.height)} name="draft-wire-handle" renderOrder={11}
    onPointerDown={event => {
      if (event.button !== 0 || !onMove) return
      event.stopPropagation()
      const start = startDeviceDrag(event.ray, position)
      if (!start) return
      drag.current = { ...start, pointerId: event.pointerId, moved: false, target: event.target }
      event.target.setPointerCapture?.(event.pointerId); onDraggingChange?.(true)
    }} onPointerMove={event => {
      const current = drag.current
      if (!current || current.pointerId !== event.pointerId) return
      event.stopPropagation()
      const point = deviceDragPosition(event.ray, current, scene)
      if (!point) return
      current.moved ||= Math.hypot(point.x-position[0],point.z-position[2]) > 0.001
      const targetPositions = new Map()
      const result = onFindSnap?.({x:point.x/scene.sourceScale,y:point.z/scene.sourceScale}, symbol => {
        const rendered = scene.symbols.find(s => s.id === symbol.id)
        if (!rendered) return Infinity
        const connector = deviceConnector(devicePlacement(rendered,scene,rendered.presentation?.family || 'unknown'))
        const projected = new Vector3(...connector).project(camera)
        if (projected.z < -1 || projected.z > 1 || Math.abs(projected.x) > 1 || Math.abs(projected.y) > 1) return Infinity
        targetPositions.set(`${symbol.id}:${symbol.terminalId}`,connector)
        return Math.hypot((projected.x-pointer.x)*size.width/2,(projected.y-pointer.y)*size.height/2)
      },16,(sourcePoint,wire) => {
        const rendered = scene.draftWires.find(w => w.id === wire.id)
        if (!rendered?.points.length) return Infinity
        const target = [sourcePoint.x*scene.sourceScale,rendered.points[0][1],sourcePoint.y*scene.sourceScale]
        const projected = new Vector3(...target).project(camera)
        if (projected.z < -1 || projected.z > 1) return Infinity
        targetPositions.set(`path:${wire.id}`,target)
        return Math.hypot((projected.x-pointer.x)*size.width/2,(projected.y-pointer.y)*size.height/2)
      },true)
      const targets = Array.isArray(result) ? result : result ? [result] : []
      const choices = targets.map(target => ({...target,
        displayPosition:target.kind === 'junction'
          ? [target.point.x*scene.sourceScale,targetPositions.get(`path:${target.wireId}`)[1],target.point.y*scene.sourceScale]
          : targetPositions.get(`${target.symbolId}:${target.terminalId}`)}))
      current.choices = choices
      const snap = targets.length === 1 ? targets[0] : null
      current.snap = snap ?? null
      setSnapPreview(snap ? {position:choices[0].displayPosition} : null)
      ref.current?.position.set(snap ? snap.point.x*scene.sourceScale : point.x,position[1],
        snap ? snap.point.y*scene.sourceScale : point.z); invalidate()
    }} onPointerUp={e => finish(e,true)} onPointerCancel={e => finish(e,false)} onLostPointerCapture={e => finish(e,false)}>
    <sphereGeometry args={[1,12,8]} /><meshBasicMaterial color={snapPreview ? '#13816c' : '#2563eb'} depthTest={false} />
  </mesh>{snapPreview && <mesh ref={magnetRef} name="wire-device-magnet-3d" position={snapPreview.position}
    scale={wireHandleRadius(snapPreview.position,camera,size.height,10)} renderOrder={10} raycast={() => null}>
    <sphereGeometry args={[1,16,12]} />
    <meshBasicMaterial color="#13816c" wireframe depthTest={false} />
  </mesh>}</group>
}

export function DraftWiring3D({ scene, selectedWireId, onSelectWire, onMoveWirePoint, onFindWireDeviceSnap, onChooseWireTarget, onDraggingChange }) {
  const selectedNetwork=scene.draftWires?.find(w=>w.id===selectedWireId)?.networkId
  // Scale tubing with the devices, not the arbitrary source-page preview size.
  // This is visual thickness only, never a conduit diameter or quantity input.
  const radius = ROUTE_DISPLAY_RADIUS * (scene.unitsPerMeter ?? 1)
  const runs = useMemo(() => displayWiringRuns((scene.draftWires || []).flatMap(wire =>
    wiringRuns(wire.segments,wire.id,s => wiringAppearance(wire,false,s).color)
      .map(run=>({...run,connectionAnchors:wire.connectionAnchors,
        spread:wire.installationMethod==='concealed_in_ceiling' && !run.segment.previewDrop}))),radius),[scene.draftWires,radius])
  return <group name="draft-observed-wiring">{(scene.draftWires || []).map(wire => <group key={wire.id} name={`wire-${wire.id}`}
    userData={{ wireId: wire.id, previewOnly: true, illustrativeHeight: wire.illustrativeHeight,
      provenance: wire.origin ?? 'observed', installationMethod: wire.installationMethod, lineStyle: wire.lineStyle }}>
    {runs.filter(run=>run.ownerId===wire.id).map(run => <WiringTube3D key={run.id} run={run} radius={radius}
      xray={wire.installationMethod==='concealed_under_floor' || selectedWireId===wire.id}
      color={wiringAppearance(wire,selectedWireId===wire.id || Boolean(selectedNetwork && wire.networkId===selectedNetwork),run.segment).color}
      onClick={onSelectWire ? event=>{event.stopPropagation();onSelectWire(wire.id,event)} : undefined} />)}
    {onMoveWirePoint && (selectedWireId === wire.id || Boolean(selectedNetwork && wire.networkId===selectedNetwork)) && wire.points.map((p,index) => <WireHandle key={index} position={p} scene={scene}
      onFindSnap={onFindWireDeviceSnap ? (point,distance,threshold,pathDistance,allTargets) => onFindWireDeviceSnap(wire.id,index,point,distance,threshold,pathDistance,allTargets) : undefined}
      onChooseTarget={choices => onChooseWireTarget?.(wire.id,index,choices)}
      onMove={onMoveWirePoint ? (point,snap) => snap ? onMoveWirePoint(wire.id,index,point,snap) : onMoveWirePoint(wire.id,index,point) : undefined} onDraggingChange={onDraggingChange} />)}
  </group>)}</group>
}
