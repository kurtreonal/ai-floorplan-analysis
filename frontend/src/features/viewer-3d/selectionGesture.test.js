import { expect, it } from 'vitest'
import { selectionGesture } from './selectionGesture.js'
const p=(x,y,extra={})=>({pointerId:1,button:0,clientX:x,clientY:y,...extra})

it('accepts a small click independently of camera scale but rejects orbit movement and return trips',()=>{
  const gate=selectionGesture()
  gate.down(p(10,10));gate.up(p(13,13));expect(gate.canSelect({delta:4})).toBe(true)
  gate.down(p(10,10));gate.move(p(100,100));gate.up(p(10,10))
  expect(gate.canSelect({delta:0})).toBe(false)
  gate.down(p(10,10));gate.up(p(10,10));expect(gate.canSelect({delta:6})).toBe(false)
})

it.each(['cancel','lost','outside','multi','right'])('does not select after %s, and a later normal click recovers',reason=>{
  const gate=selectionGesture()
  gate.down(p(10,10,reason==='right'?{button:2}:{}))
  if(reason==='cancel')gate.cancel()
  if(reason==='lost')gate.lost(p(10,10))
  if(reason==='multi'){gate.down(p(11,11,{pointerId:2,pointerType:'touch'}));gate.up(p(11,11,{pointerId:2}))}
  gate.up(p(10,10),reason!=='outside')
  expect(gate.canSelect({})).toBe(false)
  gate.down(p(20,20));gate.up(p(20,20));gate.lost(p(20,20)) // Normal release after pointerup is harmless.
  expect(gate.canSelect({})).toBe(true)
})
