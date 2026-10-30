import { useEffect } from 'react'
import { useThree } from '@react-three/fiber'
import { PMREMGenerator } from 'three'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'

// Reflection studio only: never adds objects to the authoritative building.
export function StudioEnvironment() {
  const { gl, scene, invalidate } = useThree()
  useEffect(() => {
    const previous = scene.environment
    const previousIntensity = scene.environmentIntensity
    const generator = new PMREMGenerator(gl)
    const studio = new RoomEnvironment()
    const target = generator.fromScene(studio, .04)
    // R3F owns this mutable Three.Scene, not React state; restore on teardown.
    // eslint-disable-next-line react-hooks/immutability
    scene.environment = target.texture
    scene.environmentIntensity = .18
    studio.dispose()
    generator.dispose()
    invalidate()
    return () => {
      scene.environment = previous
      scene.environmentIntensity = previousIntensity
      target.dispose()
    }
  }, [gl, scene, invalidate])
  return null
}
