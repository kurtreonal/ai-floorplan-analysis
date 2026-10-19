/* @vitest-environment jsdom */
import { act, cleanup, fireEvent, renderHook } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useSpatialDrawing } from './useSpatialDrawing.js'

afterEach(cleanup)
const options=()=>({tool:'wire',scene:{sourceScale:.1,unitsPerMeter:1,width:20,depth:20},
  context:{pixels_per_meter:10,floor_elevation_meters:12},draft:{symbols:[],walls:[],wirings:[]},
  method:'concealed_in_ceiling',editingSession:1,onAddWire:vi.fn(),onAddWall:vi.fn(),onPendingChange:vi.fn(),onToolChange:vi.fn(),snapping:false})

it('is inert with no drawing tool selected',()=>{
  const h=renderHook(()=>useSpatialDrawing({...options(),tool:undefined}))
  expect(h.result.current.active).toBe(false)
  expect(h.result.current.vertices).toEqual([])
  expect(h.result.current.hover).toBeNull()
})

it('commits one multi-point path at the explicit datum elevation and freezes settings during a stroke',()=>{
  const props=options(), h=renderHook(p=>useSpatialDrawing(p),{initialProps:props})
  expect(h.result.current.enabled).toBe(false)
  act(()=>h.result.current.setOption('elevation','14.8'))
  expect(h.result.current.enabled).toBe(true)
  for(const point of [{x:20,y:30},{x:80,y:30},{x:80,y:90}])act(()=>h.result.current.pointer(point,{},true))
  expect(props.onAddWire).not.toHaveBeenCalled()
  act(()=>h.result.current.setOption('elevation','20'))
  expect(h.result.current.settings.elevation).toBe('14.8')
  act(()=>fireEvent.keyDown(window,{key:'Enter'}))
  expect(props.onAddWire).toHaveBeenCalledExactlyOnceWith([{x:20,y:30},{x:80,y:30},{x:80,y:90}],expect.any(Array),{elevation_meters:14.8,circuit_id:null})
  expect(props.onPendingChange).toHaveBeenLastCalledWith(false)
  expect(props.onToolChange).toHaveBeenCalledWith('select')
  h.rerender({...props,tool:'select',editingSession:2,draft:{symbols:[],walls:[],wirings:[]}})
  expect(h.result.current.keepCanvas).toBe(true) // Last-shape undo must not remount/reset the camera.
})
it('cancels an active wire, backspaces and invalidates undo sessions without saving',()=>{
  const props=options(),h=renderHook(p=>useSpatialDrawing(p),{initialProps:props})
  act(()=>h.result.current.setOption('elevation','14.8'))
  for(const point of [{x:20,y:30},{x:80,y:30}])act(()=>h.result.current.pointer(point,{},true))
  act(()=>fireEvent.keyDown(window,{key:'Backspace'}))
  expect(h.result.current.vertices).toHaveLength(1)
  h.rerender({...props,editingSession:2})
  expect(h.result.current.vertices).toEqual([])
  act(()=>h.result.current.pointer({x:100,y:100},{},true))
  act(()=>fireEvent.keyDown(window,{key:'Escape'}))
  expect(h.result.current.vertices).toEqual([])
  expect(props.onAddWire).not.toHaveBeenCalled()
})
it('retains a failed finish for correction instead of dropping the stroke',()=>{
  const props=options();props.onAddWire.mockReturnValue(false)
  const h=renderHook(p=>useSpatialDrawing(p),{initialProps:props})
  act(()=>h.result.current.setOption('elevation','14.8'))
  for(const point of [{x:20,y:30},{x:80,y:30}])act(()=>h.result.current.pointer(point,{},true))
  act(()=>h.result.current.finish())
  expect(h.result.current.vertices).toHaveLength(2)
  expect(props.onToolChange).not.toHaveBeenCalled()
})
it('continues configured walls through the shared command and preserves each successful segment on finish',()=>{
  const props={...options(),tool:'draw'},h=renderHook(p=>useSpatialDrawing(p),{initialProps:props})
  act(()=>{h.result.current.setOption('thickness','.2');h.result.current.setOption('height','3');h.result.current.setOption('length','5')})
  for(const point of [{x:20,y:30},{x:50,y:70},{x:80,y:70}])act(()=>h.result.current.pointer(point,{},true))
  expect(props.onAddWall).toHaveBeenCalledTimes(2)
  expect(props.onAddWall.mock.calls[0][0]).toMatchObject({start:{x:20,y:30},end:{x:50,y:70},height_meters:3,thickness_meters:.2,estimated_thickness_pixels:2})
  act(()=>h.result.current.finish())
  expect(props.onAddWall).toHaveBeenCalledTimes(2)
  expect(props.onPendingChange).toHaveBeenLastCalledWith(false)
})
it('offers an overlap chooser, rejects stale choices and starts clean after a tool/session change',()=>{
  const props=options();props.snapping=true;props.draft.symbols=['symbol-0001','symbol-0002'].map(id=>({id,center:{x:50,y:50}}))
  const h=renderHook(p=>useSpatialDrawing(p),{initialProps:props})
  act(()=>h.result.current.setOption('elevation','14.8'))
  act(()=>h.result.current.pointer({x:50,y:50},{},true))
  expect(h.result.current.choices).toHaveLength(2)
  expect(h.result.current.vertices).toHaveLength(0)
  const choice=h.result.current.choices[1]
  act(()=>h.result.current.choose(choice))
  expect(h.result.current.vertices[0].snap.id).toBe('symbol-0002')
  h.rerender({...props,editingSession:2})
  act(()=>h.result.current.pointer({x:50,y:50},{},true))
  h.rerender({...props,editingSession:3})
  expect(h.result.current.choices).toBeUndefined()
  act(()=>h.result.current.choose(choice))
  expect(h.result.current.vertices).toHaveLength(0)
  act(()=>h.result.current.pointer({x:100,y:100},{},true))
  expect(h.result.current.vertices[0].point).toEqual({x:100,y:100})
})
