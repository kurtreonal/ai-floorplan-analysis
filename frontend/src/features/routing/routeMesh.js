import { Quaternion, Vector3 } from 'three'

// Display-only tube thickness; never used for conductor sizing or takeoff.
export const ROUTE_DISPLAY_RADIUS = 0.006

export function routeCylinder(start, end) {
  if (![...start, ...end].every(Number.isFinite)) throw new Error('Invalid route coordinates.')
  const a = new Vector3(...start), b = new Vector3(...end), direction = b.clone().sub(a)
  const length = direction.length()
  if (length <= 0) return null
  return { position: a.clone().add(b).multiplyScalar(.5).toArray(), length,
    quaternion: new Quaternion().setFromUnitVectors(new Vector3(0, 1, 0), direction.normalize()).toArray() }
}
