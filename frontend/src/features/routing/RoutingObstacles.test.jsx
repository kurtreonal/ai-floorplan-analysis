/* @vitest-environment jsdom */
import { useState } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { RoutingObstacles } from './RoutingObstacles.jsx'
import { obstacleRows } from './routeObstacles.js'

afterEach(cleanup)
const obstacle = { floor_id: 2, min_x: 1, min_y: 2, max_x: 3, max_y: 4, bottom: -1, top: 0 }
function Fixture() {
  const [rows, setRows] = useState(obstacleRows([obstacle, { ...obstacle, min_x: 2 }], 2))
  return <RoutingObstacles rows={rows} onChange={setRows} />
}

it('preserves remaining row values on removal and adds blank, required bounds', () => {
  render(<Fixture />)
  fireEvent.click(screen.getByRole('button', { name: 'Remove circuit obstacle 1' }))
  expect(screen.getByLabelText('Circuit obstacle 1 minimum x (m)').value).toBe('2')
  fireEvent.click(screen.getByRole('button', { name: 'Add circuit obstacle' }))
  const field = screen.getByLabelText('Circuit obstacle 2 minimum x (m)')
  expect(field.value).toBe('')
  expect(field.required).toBe(true)
  expect(field.getAttribute('aria-invalid')).toBe('true')
  expect(document.getElementById(field.getAttribute('aria-describedby')).textContent).toContain('finite numbers')
})

it('disables entry and removal during requests', () => {
  const changed = vi.fn()
  render(<RoutingObstacles rows={obstacleRows([obstacle], 2)} onChange={changed} disabled />)
  expect(screen.getByRole('button', { name: 'Add circuit obstacle' }).disabled).toBe(true)
  expect(screen.getByRole('button', { name: 'Remove circuit obstacle 1' }).disabled).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: 'Add circuit obstacle' }))
  fireEvent.change(screen.getByLabelText('Circuit obstacle 1 minimum x (m)'), { target: { value: '8' } })
  expect(changed).not.toHaveBeenCalled()
})

it('enforces the backend list limit without adding another row', () => {
  const changed = vi.fn()
  render(<RoutingObstacles rows={obstacleRows(Array.from({ length: 128 }, () => obstacle), 2)} onChange={changed} />)
  const add = screen.getByRole('button', { name: 'Add circuit obstacle' })
  expect(add.disabled).toBe(true)
  fireEvent.click(add)
  expect(changed).not.toHaveBeenCalled()
})
