import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import { useThree } from '@react-three/fiber'
import { MOUSE } from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'


export const ViewerCameraControls = forwardRef(function ViewerCameraControls(
  { onReady, target, extent, enabled = true, panMode = false },
  ref,
) {
  const { camera, gl, invalidate } = useThree()
  const domElement = gl.domElement
  const controlsRef = useRef(null)
  const [targetX, targetY, targetZ] = target || [0, 0, 0]

  useImperativeHandle(ref, () => ({
    reset() {
      controlsRef.current?.reset()
      controlsRef.current?.update()
      invalidate()
    },
    top() {
      const controls = controlsRef.current
      if (!controls) return
      camera.position.set(controls.target.x, controls.target.y + (extent || 20) * 1.6, controls.target.z + 0.001)
      controls.update()
      invalidate()
    },
    front() {
      const controls = controlsRef.current
      if (!controls) return
      camera.position.set(controls.target.x, controls.target.y + (extent || 20) * 0.3, controls.target.z + (extent || 20) * 1.6)
      controls.update()
      invalidate()
    },
  }), [camera, extent, invalidate])

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
    controlsRef.current.mouseButtons.LEFT = panMode ? MOUSE.PAN : MOUSE.ROTATE
  }, [enabled, panMode, targetX, targetY, targetZ, extent])

  return null
})
