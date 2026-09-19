/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { RoutingPanel } from './RoutingPanel.jsx'
import { routingRequest } from '../../api/routing.js'
vi.mock('../../api/routing.js', () => ({ routingRequest: vi.fn() }))
afterEach(() => { cleanup(); vi.clearAllMocks() })

it('submits explicit elevations and saved target identity, displaying backend lengths', async () => {
  const layout = { id: 5, project_id: 1, project_floor_id: 2, version_number: 3,
    geometry: { walls: [], symbols: [{ id: 'manual:1', class: { name: 'Outlet' }, position: { x: 2, y: 1 } }] } }
  const saved = { version_number: 4, result: { total_meters: 7, horizontal_meters: 4, vertical_meters: 3 }, stale: false }
  routingRequest.mockResolvedValue(saved)
  const onSaved = vi.fn()
  render(<RoutingPanel layout={layout} record={saved} onSaved={onSaved} />)
  expect(screen.getByText(/7.000 m total/)).toBeTruthy()
  for (const [label, value] of [['Panel x (m)', '1'], ['Panel y (m)', '1'], ['Panel elevation (m)', '3'], ['Service elevation (m)', '3'], ['Target elevation (m)', '3']]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } })
  }
  fireEvent.submit(screen.getByRole('button', { name: 'Calculate and save route' }).closest('form'))
  await waitFor(() => expect(onSaved).toHaveBeenCalledWith(saved))
  const request = routingRequest.mock.calls[0][1].configuration
  expect(request.target).toMatchObject({ symbol_id: 'manual:1', x: 2, y: 1, elevation_meters: 3 })
  expect(request.floors[0].expected_layout_version).toBe(3)
})
