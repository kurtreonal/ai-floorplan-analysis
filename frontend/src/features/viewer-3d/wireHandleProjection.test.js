import { expect, it } from 'vitest'
import { OrthographicCamera, PerspectiveCamera } from 'three'
import { wireHandleRadius } from './wireHandleProjection.js'

it('keeps a seven-pixel 3D handle usable at different distances and zoom levels',()=>{
  const camera = new PerspectiveCamera(50,1,.01,100)
  camera.updateMatrixWorld()
  const near = wireHandleRadius([0,0,-10],camera,600)
  expect(wireHandleRadius([0,0,-20],camera,600)).toBeCloseTo(near*2)
  camera.zoom=2; camera.updateProjectionMatrix()
  expect(wireHandleRadius([0,0,-10],camera,600)).toBeCloseTo(near/2)
  const orthographic = new OrthographicCamera(-5,5,5,-5,.01,100)
  orthographic.updateMatrixWorld()
  expect(wireHandleRadius([0,0,-10],orthographic,600)).toBeCloseTo(7*10/600)
  expect(wireHandleRadius([0,0,-20],orthographic,600)).toBeCloseTo(7*10/600)
})
