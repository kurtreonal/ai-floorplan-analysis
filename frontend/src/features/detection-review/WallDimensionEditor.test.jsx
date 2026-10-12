/* @vitest-environment jsdom */
import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {afterEach,it,expect,vi} from 'vitest'
import {WallDimensionEditor} from './WallDimensionEditor.jsx'
afterEach(cleanup)
const wall={id:'wall-0001',start:{x:20,y:30},end:{x:120,y:30},estimated_thickness_pixels:10}
it('converts explicit numeric units and anchors start, while unscaled plans retain pixels',()=>{
  const update=vi.fn()
  const {rerender}=render(<WallDimensionEditor wall={wall} pixelsPerMeter={100} onUpdate={update} />)
  fireEvent.change(screen.getByLabelText('Length unit'),{target:{value:'cm'}})
  fireEvent.change(screen.getByLabelText('Exact centerline length'),{target:{value:'250'}})
  fireEvent.click(screen.getByText('Apply length'))
  expect(update.mock.calls[0][0]).toMatchObject({start:{x:20,y:30},end:{x:270,y:30},estimated_thickness_pixels:10})
  rerender(<WallDimensionEditor wall={wall} onUpdate={update} />)
  expect(screen.getByLabelText('Length unit').disabled).toBe(true)
  fireEvent.change(screen.getByLabelText('Exact centerline length'),{target:{value:'250'}})
  fireEvent.click(screen.getByText('Apply length'))
  expect(update.mock.calls[1][0].end.x).toBe(270)
  expect(screen.getByText(/No confirmed page scale/)).toBeTruthy()
})
