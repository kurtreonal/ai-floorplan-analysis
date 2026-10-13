import { expect, it } from 'vitest'
import { Euler, PerspectiveCamera, Quaternion, Vector3 } from 'three'
import { advanceCameraMovement, cameraMovement, isMovementKey, turnSpectatorCamera } from './cameraMovement.js'

const facing = new Quaternion().setFromEuler(new Euler(-Math.PI/4,Math.PI/2,0,'YXZ'))
it.each([['w','arrowup'],['s','arrowdown'],['a','arrowleft'],['d','arrowright']])('maps %s and %s to the same POV-relative movement', (key, arrow) => {
  expect(cameraMovement(facing,new Set([key]))).toEqual(cameraMovement(facing,new Set([arrow])))
})
it('includes pitch, strafes in local right, and has no pole singularity', () => {
  const forward = cameraMovement(facing,new Set(['w']))
  expect(forward.y).toBeCloseTo(-Math.SQRT1_2)
  expect(forward.x).toBeCloseTo(-Math.SQRT1_2)
  expect(cameraMovement(facing,new Set(['d'])).dot(forward)).toBeCloseTo(0)
  const top = new Quaternion().setFromEuler(new Euler(-Math.PI/2,0,0))
  expect(cameraMovement(top,new Set(['w'])).y).toBeCloseTo(-1)
})
it('normalizes diagonals, cancels opposites, and supports independent vertical flight', () => {
  expect(cameraMovement(facing,new Set(['w','d','e'])).length()).toBeCloseTo(1)
  expect(cameraMovement(facing,new Set(['w','s','a','d']))).toEqual(new Vector3())
  expect(cameraMovement(facing,new Set(['e']))).toEqual(new Vector3(0,1,0))
  expect(isMovementKey('ArrowUp')).toBe(true)
  expect(isMovementKey('Escape')).toBe(false)
})
function simulate(fps, sprint = false) {
  let velocity = new Vector3(), position = new Vector3()
  for(let frame=0;frame<fps;frame++) {
    const step = advanceCameraMovement(velocity,facing,new Set(['w']),20,1/fps,sprint)
    velocity = step.velocity; position.add(step.displacement)
  }
  return { position, velocity }
}
it('smoothly accelerates and integrates the same path at 30, 60 and 144 FPS', () => {
  const first = advanceCameraMovement(new Vector3(),facing,new Set(['w']),20,1/60)
  expect(first.velocity.length()).toBeGreaterThan(0)
  expect(first.velocity.length()).toBeLessThan(7)
  expect(simulate(30).position.distanceTo(simulate(144).position)).toBeLessThan(1e-10)
  expect(simulate(60).position.distanceTo(simulate(144).position)).toBeLessThan(1e-10)
})
it('Shift triples speed, brakes after release, stops rendering, and bounds resume time', () => {
  expect(simulate(60,true).position.length()/simulate(60).position.length()).toBeCloseTo(3)
  let velocity = simulate(60).velocity
  const braking = advanceCameraMovement(velocity,facing,new Set(),20,1/60)
  expect(braking.velocity.length()).toBeLessThan(velocity.length())
  expect(braking.displacement.length()).toBeGreaterThan(0)
  let step
  for(let i=0;i<120;i++) {
    step = advanceCameraMovement(velocity,facing,new Set(),20,1/60)
    velocity = step.velocity
  }
  expect(step.active).toBe(false)
  expect(step.velocity).toEqual(new Vector3())
  expect(advanceCameraMovement(new Vector3(),facing,new Set(['w']),20,20).displacement)
    .toEqual(advanceCameraMovement(new Vector3(),facing,new Set(['w']),20,.05).displacement)
})
it('right-drag changes look, not position, clamps pitch and preserves target distance', () => {
  const camera = new PerspectiveCamera(), target = new Vector3(0,0,-10)
  const before = camera.position.clone()
  turnSpectatorCamera(camera,target,100,50)
  expect(camera.position).toEqual(before)
  expect(target.x).toBeGreaterThan(0)
  expect(target.y).toBeLessThan(0)
  expect(camera.position.distanceTo(target)).toBeCloseTo(10)
  turnSpectatorCamera(camera,target,0,100000)
  expect(new Euler().setFromQuaternion(camera.quaternion,'YXZ').x).toBeCloseTo(-Math.PI/2+.01)
})
