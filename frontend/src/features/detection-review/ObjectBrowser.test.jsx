/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ObjectBrowser } from './ObjectBrowser.jsx'

afterEach(cleanup)
const draft = {
  symbols: [
    { id: 's-10', center: { x: 20, y: 30 }, type: 'receptacle' },
    { id: 's-2', center: { x: 20, y: 30 } },
  ],
  wirings: [{ id: 'w-1', name: 'East run', circuit_id: 'LP-2', points: [{ x: 0, y: 0 }, { x: 20, y: 30 }] },
    { id: 'w-2', name: 'West run', circuit_ref: 'LP-3', disposition: 'rejected' }],
  walls: [{ id: 'wall-1', name: 'Partition' }], rooms: [],
}
const presentations = { 's-10': { label: 'Outlet', family: 'outlet' }, 's-2': { label: 'Outlet', originalLabel: 'Duplex' } }
const results = name => within(screen.getByRole('list', { name: `${name} results` }))

it('keeps co-located devices distinct and selects only the exact ID without mutating source', () => {
  const before = structuredClone(draft), select = vi.fn()
  const { rerender } = render(<ObjectBrowser draft={draft} presentations={presentations} onSelect={select} />)
  const buttons = results('Devices').getAllByRole('button')
  expect(buttons.map(button => button.textContent)).toEqual(['Outlets-2', 'Outlets-10'])
  fireEvent.click(buttons[1])
  expect(select).toHaveBeenCalledExactlyOnceWith({ kind: 'symbol', id: 's-10' })
  rerender(<ObjectBrowser draft={draft} presentations={presentations} selected={{ kind: 'symbol', id: 's-10' }} onSelect={select} />)
  expect(results('Devices').getByRole('button', { pressed: true }).textContent).toContain('s-10')
  expect(draft).toEqual(before)
})

it.each(['outlet', 'receptacle', 's-10', ' ＯＵＴＬＥＴ  s-10 '])('searches device label, type and ID: %s', query => {
  render(<ObjectBrowser draft={draft} presentations={presentations} onSelect={vi.fn()} />)
  fireEvent.change(screen.getByLabelText('Search devices'), { target: { value: query } })
  expect(results('Devices').getByRole('button', { name: /s-10/ })).toBeTruthy()
})

it('retains independent queries but excludes deleted items from search and active counts', () => {
  const select = vi.fn(), before = structuredClone(draft)
  render(<ObjectBrowser draft={draft} presentations={presentations} onSelect={select} />)
  fireEvent.change(screen.getByLabelText('Search devices'), { target: { value: 'duplex' } })
  fireEvent.click(screen.getByRole('tab', { name: 'Wiring' }))
  for (const query of ['east', 'lp-2', 'w-1']) {
    fireEvent.change(screen.getByLabelText('Search wiring'), { target: { value: query } })
    expect(results('Wiring').getAllByRole('button')).toHaveLength(1)
    expect(results('Wiring').getByRole('button').textContent).toContain('w-1')
  }
  fireEvent.change(screen.getByLabelText('Search wiring'), { target: { value: 'lp-3' } })
  expect(results('Wiring').queryByRole('button')).toBeNull()
  expect(screen.getByText('0 of 1')).toBeTruthy()
  expect(screen.getByText('No matching wiring.')).toBeTruthy()
  expect(select).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('tab', { name: 'Walls' }))
  for (const query of ['partition', 'wall-1']) {
    fireEvent.change(screen.getByLabelText('Search walls'), { target: { value: query } })
    expect(results('Walls').getAllByRole('button')).toHaveLength(1)
  }
  fireEvent.click(screen.getByRole('tab', { name: 'Devices' }))
  expect(screen.getByLabelText('Search devices').value).toBe('duplex')
  expect(results('Devices').getByRole('button').textContent).toContain('s-2')
  fireEvent.click(screen.getByRole('tab', { name: 'Wiring' }))
  expect(screen.getByLabelText('Search wiring').value).toBe('lp-3')
  expect(draft).toEqual(before)
})

it('supports roving keyboard tabs, clear/empty states and disabled result selection', () => {
  const select = vi.fn()
  render(<ObjectBrowser draft={draft} presentations={presentations} disabled onSelect={select} />)
  const devices = screen.getByRole('tab', { name: 'Devices' })
  devices.focus()
  fireEvent.keyDown(devices, { key: 'ArrowRight' })
  expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Wiring', selected: true }))
  fireEvent.keyDown(document.activeElement, { key: 'End' })
  expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Walls', selected: true }))
  fireEvent.keyDown(document.activeElement, { key: 'ArrowRight' })
  expect(document.activeElement).toBe(devices)
  expect(screen.getAllByRole('tab').filter(tab => tab.tabIndex === 0)).toHaveLength(1)
  const input = screen.getByLabelText('Search devices')
  fireEvent.change(input, { target: { value: 'not present' } })
  expect(screen.getByText('No matching devices.')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Clear devices search' }))
  expect(input.value).toBe('')
  expect(document.activeElement).toBe(input)
  fireEvent.click(results('Devices').getAllByRole('button')[0])
  expect(select).not.toHaveBeenCalled()
})
