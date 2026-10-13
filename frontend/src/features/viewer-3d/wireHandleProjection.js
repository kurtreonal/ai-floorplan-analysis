import { Vector3 } from 'three'

// Visual edit targets in CSS pixels, never physical conduit dimensions.
export function wireHandleRadius(position, camera, viewportHeight, pixels = 7) {
  if (!camera || !(viewportHeight > 0)) return .02
  const depth = Math.abs(new Vector3(...position).applyMatrix4(camera.matrixWorldInverse).z)
  const projection = Math.abs(camera.projectionMatrix.elements[5])
  return projection > 0 ? pixels * 2 * (camera.isOrthographicCamera ? 1 : Math.max(.01,depth)) / (projection * viewportHeight) : .02
}
