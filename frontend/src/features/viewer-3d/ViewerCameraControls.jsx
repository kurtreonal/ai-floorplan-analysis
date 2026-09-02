import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import { useThree } from '@react-three/fiber'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'


export const ViewerCameraControls = forwardRef(function ViewerCameraControls(
  { onReady },
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
  }), [invalidate])

  useEffect(() => {
    const controls = new OrbitControls(camera, gl.domElement)
    controls.enableRotate = true
    controls.enablePan = true
    controls.enableZoom = true
    controls.minDistance = 2
    controls.maxDistance = 80
    controls.target.set(0, 0, 0)
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
  }, [camera, gl, invalidate, onReady])

  return null
})
