import { expect, it } from 'vitest'
import { snapWiringPoint, withWiringMethod } from './wireDrawing.js'
import { wiringAppearance } from './wiringAppearance.js'

const draft = { symbols: [{ id:'outlet', center:{ x:100,y:100 }, disposition:'unresolved' },
  { id:'removed',center:{x:200,y:200},disposition:'rejected' },
  { id:'homerun',center:{x:300,y:300} }],
  wirings:[{id:'branch',points:[{x:100,y:110},{x:400,y:110}]}] }
it('magnetizes to exact live device anchors ahead of nearby wiring, without modifying geometry', () => {
  const before = structuredClone(draft)
  expect(snapWiringPoint({x:105,y:108},draft)).toEqual({x:100,y:100,snapped:true,kind:'device',id:'outlet'})
  expect(snapWiringPoint({x:205,y:202},draft).snapped).toBe(false)
  expect(snapWiringPoint({x:300,y:300},draft,{homerun:{family:'annotation'}}).snapped).toBe(false)
  expect(draft).toEqual(before)
})
it('snaps to wire endpoints and segment interiors with zoom-adjusted tolerance and respects removals', () => {
  expect(snapWiringPoint({x:395,y:115},draft)).toMatchObject({x:400,y:110,kind:'wire'})
  expect(snapWiringPoint({x:250,y:116},draft)).toMatchObject({x:250,y:110,kind:'wire'})
  expect(snapWiringPoint({x:250,y:116},draft,{},3).snapped).toBe(false)
  expect(snapWiringPoint({x:250,y:116},{...draft,wirings:[{...draft.wirings[0],disposition:'rejected'}]}).snapped).toBe(false)
})
it('stores ceiling/under-floor intent and line style, clears stale catalog mapping but invents no depth', () => {
  const source = {id:'w',points:[{x:1,y:2},{x:5,y:2}],elevation_meters:null,wiring_legend_id:99}
  const floor = withWiringMethod(source,'concealed_under_floor')
  expect(floor).toMatchObject({installation_method:'concealed_under_floor',line_style:'dashed',wiring_legend_id:null,elevation_meters:null})
  expect(wiringAppearance(floor).dash).toEqual([8,5])
  const ceiling = withWiringMethod(floor,'concealed_in_ceiling')
  expect(ceiling.line_style).toBe('solid'); expect(wiringAppearance(ceiling).dash).toBeUndefined()
  expect(source.wiring_legend_id).toBe(99)
})
