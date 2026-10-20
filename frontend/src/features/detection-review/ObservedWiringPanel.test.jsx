/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ObservedWiringPanel } from './ObservedWiringPanel.jsx'

afterEach(cleanup)
describe('visible wiring review', () => {
  it('removes deleted rows and selection controls while keeping the internal record for undo',()=>{
    const wire={id:'segment-0001',points:[{x:10,y:20},{x:30,y:20}],disposition:'rejected',completeness:'partial'}
    render(<ObservedWiringPanel wires={[wire]} width={400} height={300} onChange={vi.fn()} visible onVisibilityChange={vi.fn()} view="2d" />)
    expect(screen.getByText('Wiring · 0 paths')).toBeTruthy()
    expect(screen.queryByText(/segment-0001/)).toBeNull()
    expect(screen.queryByText(/Restore/)).toBeNull()
    expect(wire.disposition).toBe('rejected')
  })
  it('creates only explicit valid source traces, unresolved with no invented elevation', () => {
    const onChange = vi.fn(), onVisibilityChange = vi.fn()
    render(<ObservedWiringPanel wires={[]} width={400} height={300} onChange={onChange} visible={false} onVisibilityChange={onVisibilityChange} view="2d" />)
    fireEvent.click(screen.getByText('Add visible wiring trace'))
    fireEvent.click(screen.getByText('Apply wiring changes'))
    expect(screen.getByRole('alert').textContent).toMatch(/2–2048/)
    expect(onChange).not.toHaveBeenCalled()
    fireEvent.change(screen.getByLabelText('Source-pixel points'), { target: { value: '10,20\n30,20\n30,40' } })
    fireEvent.click(screen.getByText('Apply wiring changes'))
    expect(onChange).toHaveBeenCalledWith([{ id: 'manual-wiring-0001', points: [{ x: 10, y: 20 }, { x: 30, y: 20 }, { x: 30, y: 40 }], disposition: 'added', completeness: 'partial', elevation_meters: null }])
    expect(onVisibilityChange).toHaveBeenCalledWith(true)
  })
  it('preserves explicit elevation on edits and records removal as a tombstone', () => {
    const wire = { id: 'segment-0001', points: [{ x: 10, y: 20 }, { x: 30, y: 20 }], disposition: 'unresolved', completeness: 'partial', elevation_meters: 2.8 }
    const onChange = vi.fn()
    render(<ObservedWiringPanel wires={[wire]} width={400} height={300} onChange={onChange} visible onVisibilityChange={vi.fn()} view="2d" />)
    fireEvent.change(screen.getByLabelText('Source-pixel points segment-0001'), { target: { value: '10,20\n50,20' } })
    expect(screen.queryByLabelText('Wiring decision segment-0001')).toBeNull()
    fireEvent.click(screen.getByText('Apply wiring changes'))
    expect(onChange.mock.calls[0][0][0]).toMatchObject({ disposition: 'corrected', elevation_meters: 2.8, points: [{ x: 10, y: 20 }, { x: 50, y: 20 }] })
    fireEvent.click(screen.getByText('Remove wiring trace'))
    expect(onChange.mock.calls[1][0]).toEqual([{ ...wire, disposition: 'rejected' }])
    expect(wire.disposition).toBe('unresolved')
  })
  it('allows illustrative draft wires in 3D without granting circuit approval', () => {
    render(<ObservedWiringPanel wires={[]} width={400} height={300} onChange={vi.fn()} visible onVisibilityChange={vi.fn()} view="3d" />)
    expect(screen.getByLabelText('Show wiring').disabled).toBe(false)
    expect(screen.getByText(/Draft heights are illustrative unless set/)).toBeTruthy()
  })
  it('locks applied edits while a revision save is in flight', () => {
    const wire = { id: 'manual-wiring-0001', points: [{ x: 10, y: 20 }, { x: 30, y: 20 }], disposition: 'unresolved', completeness: 'partial', elevation_meters: null }
    render(<ObservedWiringPanel wires={[wire]} width={400} height={300} onChange={vi.fn()} visible onVisibilityChange={vi.fn()} view="2d" disabled />)
    expect(screen.getByText('Add visible wiring trace').disabled).toBe(true)
    expect(screen.getByLabelText('Source-pixel points manual-wiring-0001').closest('fieldset').disabled).toBe(true)
  })
})
