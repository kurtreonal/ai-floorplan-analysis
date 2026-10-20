/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { DraftRoomPreview } from './DraftRoomPreview.jsx'

const capture=vi.hoisted(()=>({props:null}))
vi.mock('../viewer-3d/Viewer3DCanvas.jsx',()=>({Viewer3DCanvas:props=>{capture.props=props;return <div>Shared scene</div>}}))
afterEach(cleanup)
it('collapses preview assumptions without changing scene geometry or approval state',()=>{
  const draft={rooms:[],walls:[{id:'wall',start:{x:10,y:10},end:{x:100,y:10}}],symbols:[],wirings:[]}
  const original=structuredClone(draft)
  render(<DraftRoomPreview draft={draft} width={400} height={300} layers={{walls:true}} />)
  expect(screen.queryByText(/connected devices/)).toBeNull()
  expect(screen.queryByText(/Click wiring, then drag/)).toBeNull()
  const settings=screen.getByText('3D settings'),details=settings.closest('details'),scene=capture.props.scene
  expect(details.open).toBe(false)
  fireEvent.click(settings)
  expect(details.open).toBe(true)
  expect(screen.getByText(/They do not approve or calibrate/)).toBeTruthy()
  expect(screen.getByLabelText('Source page long side (m)').value).toBe('40')
  fireEvent.click(settings)
  expect(capture.props.scene).toBe(scene)
  expect(draft).toEqual(original)
})
it('retains confirmed scale requirements and actionable invalid-geometry errors',()=>{
  const draft={rooms:[],walls:[],symbols:[{id:'bad',center:{x:NaN,y:20}}],wirings:[]}
  render(<DraftRoomPreview draft={draft} width={400} height={300} layers={{walls:true}} routingContext={{pixels_per_meter:20}} />)
  expect(screen.getByLabelText('Source page long side (m)').disabled).toBe(true)
  expect(screen.getByLabelText('Source page long side (m)').value).toBe('20')
  expect(screen.getByRole('alert').textContent).toMatch(/invalid device positions.*Correct/)
})
