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
  const flight = useRef({ keys: new Set(), velocity: new Vector3(), sprint: false })
  const stop = useCallback(() => {
    flight.current.keys.clear()
    flight.current.velocity.set(0,0,0)
    flight.current.sprint = false
  }, [])
  const [targetX, targetY, targetZ] = target || [0, 0, 0]

  useImperativeHandle(ref, () => ({
    reset() {
      stop()
      controlsRef.current?.reset()
      controlsRef.current?.update()
      invalidate()
    },
    top() {
      stop()
      const controls = controlsRef.current
      if (!controls) return
      camera.position.set(controls.target.x, controls.target.y + (extent || 20) * 1.6, controls.target.z + 0.001)
      controls.update()
      invalidate()
    },
    front() {
      stop()
      const controls = controlsRef.current
      if (!controls) return
      camera.position.set(controls.target.x, controls.target.y + (extent || 20) * 0.3, controls.target.z + (extent || 20) * 1.6)
      controls.update()
      invalidate()
    },
  }), [camera, extent, invalidate, stop])

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
    controlsRef.current = controls
    onReady?.(true)

    return () => {
      onReady?.(false)
      controls.removeEventListener('change', invalidate)
      controls.dispose()
      controlsRef.current = null
    }
  }, [camera, domElement, invalidate, onReady, targetX, targetY, targetZ, extent])

  useEffect(() => {
    if (!controlsRef.current) return
    controlsRef.current.enabled = enabled
    controlsRef.current.enableRotate = !freeFly
    controlsRef.current.mouseButtons.LEFT = panMode ? MOUSE.PAN : leftOrbit ? MOUSE.ROTATE : null
    controlsRef.current.mouseButtons.MIDDLE = MOUSE.ROTATE
    controlsRef.current.mouseButtons.RIGHT = MOUSE.PAN
    controlsRef.current.touches.ONE = leftOrbit ? TOUCH.ROTATE : null
    controlsRef.current.touches.TWO = leftOrbit ? TOUCH.DOLLY_PAN : TOUCH.DOLLY_ROTATE
    stop()
  }, [enabled, panMode, freeFly, leftOrbit, targetX, targetY, targetZ, extent, stop])

  useFrame((_, delta) => {
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
