import { Plane, Vector3 } from 'three'

export function startDeviceDrag(ray, position) {
  const plane = new Plane(new Vector3(0, 1, 0), -position[1])
  const point = ray.intersectPlane(plane, new Vector3())
  return point ? { plane, offset: new Vector3(...position).sub(point) } : null
}

export function deviceDragPosition(ray, drag, scene) {
  const point = ray.intersectPlane(drag.plane, new Vector3())
  if (!point) return null
  point.add(drag.offset)
  return { x: Math.max(0, Math.min(scene.width, point.x)), z: Math.max(0, Math.min(scene.depth, point.z)) }
}
