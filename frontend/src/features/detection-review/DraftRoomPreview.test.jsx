/* @vitest-environment jsdom */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { DraftRoomPreview } from './DraftRoomPreview.jsx'
const capture = vi.hoisted(() => ({ props: null }))
vi.mock('../viewer-3d/Viewer3DCanvas.jsx', () => ({ Viewer3DCanvas: (props) => { capture.props = props; return <div>Scene</div> } }))
afterEach(cleanup)
it('uses the shared nominal scale for actual wire length without calling it approved',()=>{
  const draft={rooms:[],walls:[],symbols:[],wirings:[{id:'w',points:[{x:10,y:20},{x:110,y:20}],disposition:'unresolved'}]}
  render(<DraftRoomPreview draft={draft} layers={{wirings:true}} width={841} height={594}
    routingContext={{pixels_per_meter:10,scale_basis:'ved_paper_ratio_draft',scale_approved:false}}/>)
  const scene=capture.props.scene,[start,end]=scene.draftWires[0].points
  expect(Math.hypot(...start.map((value,index)=>end[index]-value))/scene.unitsPerMeter).toBeCloseTo(10)
  expect(screen.getByText(/Draft paper scale is active; not independently calibrated/)).toBeTruthy()
  expect(screen.getByLabelText('Source page long side (m)').value).toBe('84.1')
})
it('preserves exact wall selection through the shared preview without rebuilding geometry',()=>{
  const draft={rooms:[],walls:[{id:'wall-1',start:{x:10,y:20},end:{x:100,y:20}}],symbols:[],wirings:[]}
  const layers={walls:true},props={draft,layers,width:400,height:300}
  const {rerender}=render(<DraftRoomPreview {...props} selected={{kind:'wall',id:'wall-1'}} />)
  const scene=capture.props.scene
  expect(capture.props.selectedWallId).toBe('wall-1')
  rerender(<DraftRoomPreview {...props} selected={{kind:'symbol',id:'device'}} />)
  expect(capture.props.selectedWallId).toBeNull()
  expect(capture.props.scene).toBe(scene)
})
it('keeps the canvas mounted after drawing and last-shape undo, preserving camera ownership',()=>{
  const draft={rooms:[],walls:[],symbols:[],wirings:[]},context={pixels_per_meter:10,floor_elevation_meters:12}
  const add=vi.fn(),{rerender}=render(<DraftRoomPreview draft={draft} width={400} height={300} routingContext={context} navigationMode="wire" onAddWire={add} />)
  act(()=>capture.props.drawing.setOption('elevation','14.8'))
  for(const point of [{x:20,y:30},{x:80,y:30}])act(()=>capture.props.drawing.pointer(point,{},true))
  act(()=>capture.props.drawing.finish())
  expect(add).toHaveBeenCalledTimes(1)
  rerender(<DraftRoomPreview draft={{...draft}} width={400} height={300} routingContext={context} navigationMode="select" editingSession={2} />)
  expect(screen.getByText('Scene')).toBeTruthy()
  expect(screen.queryByText(/No geometry yet/)).toBeNull()
})
it('shows and edits a wire-only whole-page draft without a layout approval gate', () => {
  const draft = { rooms: [], walls: [], symbols: [], wirings: [{ id: 'wire', points: [{ x: 40, y: 50 }, { x: 250, y: 150 }], disposition: 'unresolved', elevation_meters: null }] }
  const onSelect = vi.fn(), onMoveWirePoint = vi.fn()
  const { rerender } = render(<DraftRoomPreview draft={draft} width={400} height={200} onSelect={onSelect} onMoveWirePoint={onMoveWirePoint} selected={{ kind: 'wiring', id: 'wire' }} />)
  expect(screen.getByText('Scene')).toBeTruthy()
  expect(capture.props.scene.draftWires[0].points).toEqual([[1,.75,1.25],[6.25,.75,3.75]])
  expect(capture.props.selectedWireId).toBe('wire')
  capture.props.onSelectWire('wire')
  expect(onSelect).toHaveBeenCalledWith({ kind: 'wiring', id: 'wire' })
  capture.props.onMoveWirePoint('wire',1,{ x: 5, y: 3 })
  expect(onMoveWirePoint).toHaveBeenCalledWith('wire',1,{ x: 200, y: 120 })
  rerender(<DraftRoomPreview draft={draft} width={400} height={200} layers={{ wirings: false }} />)
  expect(screen.queryByText('Scene')).toBeNull()
})
it('toggles the roof independently, rescales physical presets and preserves pixel-space dragging', () => {
  const draft = { rooms: [], walls: [{ id: 'w', start: { x: 10, y: 10 }, end: { x: 90, y: 10 } }], symbols: [{ id: 's', center: { x: 50, y: 50 } }] }
  const before = structuredClone(draft), onUpdateSymbol = vi.fn()
  render(<DraftRoomPreview draft={draft} width={100} height={200} projectId={1} onUpdateSymbol={onUpdateSymbol} />)
  expect(capture.props.showRoof).toBe(false)
  expect(capture.props.scene.ceilingElevation).toBe(0.75)
  fireEvent.click(screen.getByRole('button', { name: 'Show roof' }))
  expect(capture.props.showRoof).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: 'Hide roof' }))
  expect(capture.props.showRoof).toBe(false)
  fireEvent.change(screen.getByLabelText('Source page long side (m)'), { target: { value: '20' } })
  expect(capture.props.scene.unitsPerMeter).toBe(0.5)
  expect(capture.props.scene.ceilingElevation).toBe(1.5)
  fireEvent.change(screen.getByLabelText('Wall height (m)'), { target: { value: '4' } })
  expect(capture.props.scene.ceilingElevation).toBe(2)
  capture.props.onMoveSymbol('s', { x: 3, y: 4 })
  expect(onUpdateSymbol).toHaveBeenCalledWith({ ...draft.symbols[0], center: { x: 60, y: 80 } })
  expect(draft).toEqual(before)
})

it('passes exact source-space device attachments from 3D through the same commit handler', () => {
  const draft = {walls:[],rooms:[],symbols:[{id:'s',center:{x:80.25,y:60.5}}],
    wirings:[{id:'wire',points:[{x:40,y:50},{x:250,y:150}]}]}
  const commit = vi.fn()
  render(<DraftRoomPreview draft={draft} width={400} height={200} onMoveWirePoint={commit} />)
  const snap = capture.props.onFindWireDeviceSnap('wire',1,{x:79,y:59},() => 8,16)
  expect(snap.point).toEqual(draft.symbols[0].center)
  capture.props.onMoveWirePoint('wire',1,{x:2,y:1.5},snap)
  expect(commit).toHaveBeenCalledWith('wire',1,draft.symbols[0].center,snap)
})
