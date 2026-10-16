/* @vitest-environment jsdom */
import {cleanup,render,screen,fireEvent} from '@testing-library/react'
import {afterEach,it,expect,vi} from 'vitest'
import {WiringRecoveryStatus} from './WiringRecoveryStatus.jsx'
import {WireJunctionEditor} from './WireJunctionEditor.jsx'
afterEach(cleanup)
it('explains analysis-time evidence, failed passes and unresolved devices without claiming absence or approval',()=>{
  render(<WiringRecoveryStatus report={{stop_reason:'methods_exhausted',passes:[{method:'native_local_strokes',windows:2,added_paths:1,added_contacts:1,failed_windows:1}],
    devices:[{symbol_id:'symbol-0001',state:'observed_recovered'},{symbol_id:'symbol-0002',state:'no_usable_observed_path',reason:'no_supported_path_after_search'}]}} />)
  fireEvent.click(screen.getByText('Source recovery · 1 connected · 1 unresolved'))
  expect(screen.getByText(/does not establish that wiring is absent/)).toBeTruthy()
  expect(screen.getByText(/Proposals are not human approval/)).toBeTruthy()
  expect(screen.getByText(/1 windows failed/)).toBeTruthy()
})
it('hiding advanced vertex tools does not mutate existing connections and exposes no low-level connect form',()=>{
  const wire={id:'segment-0001',points:[{x:0,y:0},{x:30,y:0}],junction_attachments:[{junction_id:'junction-0001',point_index:0}]}
  const before=structuredClone(wire),edit=vi.fn()
  render(<WireJunctionEditor wire={wire} onEdit={edit} />)
  fireEvent.click(screen.getByText('Path vertices & junctions'))
  expect(screen.getByRole('button',{name:'Detach junction at vertex'})).toBeTruthy()
  expect(screen.queryByText('Connect junction')).toBeNull()
  fireEvent.click(screen.getByText('Path vertices & junctions'))
  expect(wire).toEqual(before);expect(edit).not.toHaveBeenCalled()
})
