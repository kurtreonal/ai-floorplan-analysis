import { Plane, Vector3 } from 'three'

export function startDeviceDrag(ray, position, normal = [0, 1, 0]) {
  const direction = new Vector3(...normal).normalize()
  const plane = new Plane().setFromNormalAndCoplanarPoint(direction, new Vector3(...position))
  const point = ray.intersectPlane(plane, new Vector3())
  return point ? { plane, offset: new Vector3(...position).sub(point) } : null
}

export function deviceDragPosition(ray, drag, scene) {
  const point = ray.intersectPlane(drag.plane, new Vector3())
  if (!point) return null
  point.add(drag.offset)
  return { x: Math.max(0, Math.min(scene.width, point.x)), y: point.y, z: Math.max(0, Math.min(scene.depth, point.z)) }
}

export function mountDraggedDevice(point, placement, scene) {
  const unit = scene.unitsPerMeter ?? 1
  if (placement.mount !== 'wall') return { ...point, y: placement.position[1] }
  let best = null
  for (const wall of scene.mountingWalls || scene.walls || []) {
    const angle = -wall.rotation[1], dx = Math.cos(angle), dz = Math.sin(angle)
    const along = Math.max(-wall.size[0] / 2, Math.min(wall.size[0] / 2,
      (point.x - wall.position[0]) * dx + (point.z - wall.position[2]) * dz))
    const x = wall.position[0] + along * dx, z = wall.position[2] + along * dz
    const distance = Math.hypot(point.x - x, point.z - z)
    if (!best || distance < best.distance) best = { wall, x, z, dx, dz, distance }
  }
  if (!best || best.distance > unit + best.wall.size[2] / 2) return point
  let nx = -best.dz, nz = best.dx
  if ((point.x - best.x) * nx + (point.z - best.z) * nz < 0) { nx *= -1; nz *= -1 }
  const offset = best.wall.size[2] / 2 + placement.size[2] / 2 + .002 * unit
  const bottom = best.wall.position[1] - best.wall.size[1] / 2
  return { x: best.x + nx * offset, z: best.z + nz * offset,
    y: Math.max(bottom + placement.size[1] / 2, Math.min(bottom + best.wall.size[1] - placement.size[1] / 2, point.y)),
    anchorX: best.x, anchorZ: best.z, wallId: best.wall.id, rotation: Math.atan2(nx, nz) }
}
