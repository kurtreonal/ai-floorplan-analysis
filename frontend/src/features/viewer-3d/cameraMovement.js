import { Euler, Vector3 } from 'three'

const movementKeys = new Set(['w','a','s','d','arrowup','arrowdown','arrowleft','arrowright','q','e'])
export const isMovementKey = key => movementKeys.has(key.toLowerCase())

// Camera local -Z is forward, +X is right. Pitch is intentionally preserved.
export function cameraMovement(quaternion, keys) {
  const held = key => keys.has(key)
  const direction = new Vector3(
    Number(held('d') || held('arrowright')) - Number(held('a') || held('arrowleft')),
    0,
    Number(held('s') || held('arrowdown')) - Number(held('w') || held('arrowup')),
  ).applyQuaternion(quaternion)
  direction.y += Number(held('e')) - Number(held('q'))
  return direction.lengthSq() ? direction.normalize() : direction
}

export function advanceCameraMovement(velocity, quaternion, keys, extent, delta, sprint = false) {
  // Never leap across a plan after resuming a hidden tab.
  const dt = Math.max(0, Math.min(.05, Number.isFinite(delta) ? delta : 0))
  const speed = Math.max(.25, Math.min(20, (extent || 20) * .35)) * (sprint ? 3 : 1)
  const desired = cameraMovement(quaternion, keys).multiplyScalar(speed)
  const response = 12, decay = Math.exp(-response * dt)
  const difference = velocity.clone().sub(desired)
  // Exact exponential integration: acceleration/braking do not depend on FPS.
  const displacement = desired.clone().multiplyScalar(dt).addScaledVector(difference, (1-decay)/response)
  const nextVelocity = desired.clone().addScaledVector(difference, decay)
  const active = desired.lengthSq() > 0 || nextVelocity.lengthSq() > 1e-8
  if (!active) nextVelocity.set(0,0,0)
  return { displacement, velocity: nextVelocity, active }
}

export function turnSpectatorCamera(camera, target, dx, dy) {
  const distance = Math.max(.1, camera.position.distanceTo(target))
  const look = new Euler().setFromQuaternion(camera.quaternion, 'YXZ')
  look.y -= dx * .003
  look.x = Math.max(-Math.PI/2+.01, Math.min(Math.PI/2-.01, look.x-dy*.003))
  camera.quaternion.setFromEuler(look)
  target.copy(camera.position).add(new Vector3(0,0,-distance).applyQuaternion(camera.quaternion))
}
