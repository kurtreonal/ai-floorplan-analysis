/* @vitest-environment jsdom */
import {cleanup,render,screen} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {SourceConnectivityNotice} from './SourceConnectivityNotice.jsx'
afterEach(cleanup)
it('exposes unresolved coverage independently of analysis completion and generated routes',()=>{
  render(<SourceConnectivityNotice diagnostics summary={{state:'unresolved',connected_devices:1,unresolved_devices:4,no_usable_path_devices:2,unassessed_devices:3,unassessed_pages:1,search_incomplete:true}} />)
  expect(screen.getByRole('status').textContent).toContain('9 unresolved')
  expect(screen.getByRole('status').textContent).toContain('1 pages unassessed')
  expect(screen.getByRole('status').textContent).toContain('Generated routes are separate')
})
it('does not call zero detections connected or resolved',()=>{
  render(<SourceConnectivityNotice diagnostics summary={{state:'unavailable',connected_devices:0,unresolved_devices:0,no_usable_path_devices:0,unassessed_devices:0,unassessed_pages:0,search_incomplete:true}} />)
  expect(screen.getByRole('status').textContent).toContain('not established')
})
it('keeps diagnostic counts and approval explanations out of normal workflow feedback',()=>{
  const summary={state:'unresolved',connected_devices:2,unresolved_devices:4,search_incomplete:true}
  const before=structuredClone(summary)
  const {container}=render(<SourceConnectivityNotice summary={summary} />)
  expect(container.textContent).toBe('')
  expect(summary).toEqual(before)
})
