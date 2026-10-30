import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { MOUSE, TOUCH, Vector3 } from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { advanceCameraMovement, isMovementKey, turnSpectatorCamera } from './cameraMovement.js'


export const ViewerCameraControls = forwardRef(function ViewerCameraControls(
  { onReady, target, extent, enabled = true, panMode = false, freeFly = true, leftOrbit = true },
  ref,
) {
  const { camera, gl, invalidate } = useThree()
  const domElement = gl.domElement
  const controlsRef = useRef(null)
  const transition = useRef(null)
  const flight = useRef({ keys: new Set(), velocity: new Vector3(), sprint: false })
  const stop = useCallback(() => {
    flight.current.keys.clear()
    flight.current.velocity.set(0,0,0)
    flight.current.sprint = false
  }, [])
  const [targetX, targetY, targetZ] = target || [0, 0, 0]
  const moveTo = useCallback((destination,lookAt,duration=.4) => {
    const controls=controlsRef.current
    if (!controls) return
    stop()
    transition.current={from:camera.position.clone(),to:new Vector3(...destination),
      fromTarget:controls.target.clone(),toTarget:new Vector3(...lookAt),elapsed:0,
      duration:window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 0 : duration}
    invalidate()
  },[camera,invalidate,stop])
  const fit = useCallback(()=>{
    const distance=(extent || 20)*Math.max(1,1/(camera.aspect || 1))
    moveTo([targetX+distance,targetY+distance*.85,targetZ+distance],[targetX,targetY,targetZ])
  },[camera,extent,moveTo,targetX,targetY,targetZ])

  useImperativeHandle(ref, () => ({
    fit, isometric:fit,
    benchmarkOrbit(angle) {
      if(!import.meta.env.DEV || !controlsRef.current)return
      transition.current=null
      camera.position.set(targetX+Math.cos(angle)*(extent||20),targetY+(extent||20)*.8,targetZ+Math.sin(angle)*(extent||20))
      controlsRef.current.target.set(targetX,targetY,targetZ);controlsRef.current.update();invalidate()
    },
    focus(point,closeUpDistance,approach) { if(point){const distance=Number.isFinite(closeUpDistance)&&closeUpDistance>0?closeUpDistance:(extent||20)*.25;const direction=Array.isArray(approach)&&approach.length===3&&approach.every(Number.isFinite)?approach:[1,.8,1];moveTo(point.map((value,index)=>value+distance*direction[index]),point,1)} },
    reset() {
      stop();transition.current=null
      controlsRef.current?.reset();controlsRef.current?.update();invalidate()
    },
    top() {
      stop()
      const controls = controlsRef.current
      if (!controls) return
      moveTo([targetX,targetY+(extent||20)*1.6,targetZ+.001],[targetX,targetY,targetZ])
    },
    front() {
      stop()
      const controls = controlsRef.current
      if (!controls) return
      moveTo([targetX,targetY,targetZ+(extent||20)*1.6],[targetX,targetY,targetZ])
    },
  }), [extent, stop,fit,moveTo,targetX,targetY,targetZ,invalidate,camera.position])

  useEffect(() => {
    const controls = new OrbitControls(camera, domElement)
    controls.enableRotate = true
    controls.enablePan = true
    controls.enableZoom = true
    controls.minDistance = 0.1
    controls.maxDistance = (extent || 20) * 8
    controls.target.set(targetX, targetY, targetZ)
    controls.update()
    controls.saveState()
    controls.addEventListener('change', invalidate)
    const interrupt=()=>{transition.current=null}
    controls.addEventListener('start',interrupt)
    controlsRef.current = controls
    onReady?.(true)

    return () => {
      onReady?.(false)
      controls.removeEventListener('change', invalidate)
      controls.removeEventListener('start',interrupt)
      controls.dispose()
      controlsRef.current = null
    }
  }, [camera, domElement, invalidate, onReady, targetX, targetY, targetZ, extent])

  useEffect(() => {
    if (!controlsRef.current) return
    controlsRef.current.enabled = enabled
    controlsRef.current.enableRotate = true
    controlsRef.current.mouseButtons.LEFT = panMode ? MOUSE.PAN : leftOrbit ? MOUSE.ROTATE : null
    controlsRef.current.mouseButtons.MIDDLE = freeFly && leftOrbit ? MOUSE.PAN : MOUSE.ROTATE
    controlsRef.current.mouseButtons.RIGHT = MOUSE.PAN
    controlsRef.current.touches.ONE = leftOrbit ? TOUCH.ROTATE : null
    controlsRef.current.touches.TWO = leftOrbit ? TOUCH.DOLLY_PAN : TOUCH.DOLLY_ROTATE
    stop()
  }, [enabled, panMode, freeFly, leftOrbit, targetX, targetY, targetZ, extent, stop])

  useFrame((_, delta) => {
    const animation=transition.current
    if (animation && controlsRef.current) {
      animation.elapsed+=delta
      const t=animation.duration ? Math.min(1,animation.elapsed/animation.duration) : 1
      const eased=1-Math.pow(1-t,3)
      camera.position.lerpVectors(animation.from,animation.to,eased)
      controlsRef.current.target.lerpVectors(animation.fromTarget,animation.toTarget,eased)
      controlsRef.current.update()
      if(t===1){camera.position.copy(animation.to);controlsRef.current.target.copy(animation.toTarget);transition.current=null}
      invalidate()
    }
    if (!enabled || !freeFly || !controlsRef.current) return
    const movement = advanceCameraMovement(flight.current.velocity, camera.quaternion,
      flight.current.keys, extent, delta, flight.current.sprint)
    flight.current.velocity.copy(movement.velocity)
    if (!movement.active && movement.displacement.lengthSq() < 1e-8) return
    camera.position.add(movement.displacement)
    controlsRef.current.target.add(movement.displacement)
    controlsRef.current.update()
    if (movement.active) invalidate()
  })

  useEffect(() => {
    const viewport = domElement.closest('[aria-label="3D viewer"]') || domElement
    const move = event => {
      const controls = controlsRef.current
      if (!enabled || !freeFly || !controls || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey
        || event.target.closest?.('input,textarea,select,button,[contenteditable="true"]')
        || !viewport.contains(viewport.ownerDocument.activeElement)) return
      const key = event.key.toLowerCase()
      if (key === 'escape') { stop(); return }
      if (!isMovementKey(key) && key !== 'shift') return
      transition.current = null
      event.preventDefault()
      if (isMovementKey(key)) flight.current.keys.add(key)
      flight.current.sprint = event.shiftKey || key === 'shift'
      invalidate()
    }
    const release = event => {
      if (!isMovementKey(event.key) && event.key.toLowerCase() !== 'shift') return
      if (!flight.current.keys.size && flight.current.velocity.lengthSq() === 0) return
      flight.current.keys.delete(event.key.toLowerCase())
      flight.current.sprint = event.shiftKey && event.key.toLowerCase() !== 'shift'
      invalidate()
    }
    const leave = event => {
      if (!viewport.contains(event.relatedTarget) || event.relatedTarget?.closest?.('input,textarea,select,button,[contenteditable="true"]')) stop()
    }
    const ownerWindow = viewport.ownerDocument.defaultView
    const visibility = () => { if (viewport.ownerDocument.hidden) stop() }
    viewport.addEventListener('keydown',move)
    viewport.addEventListener('focusout',leave)
    ownerWindow.addEventListener('keyup',release)
    ownerWindow.addEventListener('blur',stop)
    viewport.ownerDocument.addEventListener('visibilitychange',visibility)
    return () => {
      stop()
      viewport.removeEventListener('keydown',move)
      viewport.removeEventListener('focusout',leave)
      ownerWindow.removeEventListener('keyup',release)
      ownerWindow.removeEventListener('blur',stop)
      viewport.ownerDocument.removeEventListener('visibilitychange',visibility)
    }
  }, [domElement, enabled, freeFly, invalidate, stop])

  useEffect(() => {
    let pointer = null
    const down = event => {
      if (!enabled || !freeFly || event.button !== 2) return
      transition.current = null
      event.preventDefault(); event.stopImmediatePropagation()
      pointer = { id: event.pointerId, x: event.clientX, y: event.clientY }
      domElement.closest('[aria-label="3D viewer"]')?.focus({ preventScroll: true })
      domElement.setPointerCapture?.(event.pointerId)
    }
    const look = event => {
      if (!pointer || event.pointerId !== pointer.id || !controlsRef.current) return
      event.preventDefault(); event.stopImmediatePropagation()
      turnSpectatorCamera(camera, controlsRef.current.target, event.clientX-pointer.x, event.clientY-pointer.y)
      pointer.x = event.clientX; pointer.y = event.clientY
      controlsRef.current.update(); invalidate()
    }
    const up = () => {
      const identity = pointer?.id
      pointer = null
      if (identity != null && domElement.hasPointerCapture?.(identity)) domElement.releasePointerCapture(identity)
    }
    const menu = event => { if (freeFly) event.preventDefault() }
    domElement.addEventListener('pointerdown',down,true)
    domElement.addEventListener('pointermove',look,true)
    domElement.addEventListener('pointerup',up,true)
    domElement.addEventListener('pointercancel',up,true)
    domElement.addEventListener('lostpointercapture',up)
    domElement.addEventListener('contextmenu',menu)
    domElement.ownerDocument.defaultView.addEventListener('blur',up)
    return () => {
      up()
      domElement.removeEventListener('pointerdown',down,true)
      domElement.removeEventListener('pointermove',look,true)
      domElement.removeEventListener('pointerup',up,true)
      domElement.removeEventListener('pointercancel',up,true)
      domElement.removeEventListener('lostpointercapture',up)
      domElement.removeEventListener('contextmenu',menu)
      domElement.ownerDocument.defaultView.removeEventListener('blur',up)
    }
  }, [camera, domElement, enabled, freeFly, invalidate])

  return null
})
