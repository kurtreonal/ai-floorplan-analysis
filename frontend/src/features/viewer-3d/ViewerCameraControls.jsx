import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import { useThree } from '@react-three/fiber'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'


export const ViewerCameraControls = forwardRef(function ViewerCameraControls(
  { onReady, target, extent },
  ref,
) {
  const { camera, gl, invalidate } = useThree()
  const controlsRef = useRef(null)

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
  }), [camera, extent, invalidate])

  useEffect(() => {
    const controls = new OrbitControls(camera, gl.domElement)
    controls.enableRotate = true
    controls.enablePan = true
    controls.enableZoom = true
    controls.minDistance = 0.1
    controls.maxDistance = (extent || 20) * 8
    controls.target.set(...(target || [0, 0, 0]))
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
  }, [camera, gl, invalidate, onReady, target, extent])

  return null
})
