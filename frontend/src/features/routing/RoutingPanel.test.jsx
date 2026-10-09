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

it('aborts an obsolete layout request and never clears the newer circuit through a late callback', async () => {
  let finish
  routingRequest.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  const layout = { id: 5, project_id: 1, project_floor_id: 2, version_number: 3,
    geometry: { walls: [], symbols: [{ id: 'manual:1', class: { name: 'Outlet' }, position: { x: 2, y: 1 } }] } }
  const onSaved = vi.fn()
  const rendered = render(<RoutingPanel layout={layout} onSaved={onSaved} />)
  for (const label of ['Panel x (m)', 'Panel y (m)', 'Panel elevation (m)', 'Service elevation (m)', 'Target elevation (m)']) {
    fireEvent.change(screen.getByLabelText(label), { target: { value: '3' } })
  }
  fireEvent.submit(screen.getByRole('button', { name: 'Calculate and save route' }).closest('form'))
  await waitFor(() => expect(routingRequest).toHaveBeenCalled())
  const signal = routingRequest.mock.calls[0][1].signal
  rendered.unmount()
  expect(signal.aborted).toBe(true)
  finish({ version_number: 4 })
  await Promise.resolve()
  expect(onSaved).not.toHaveBeenCalled()
})

it('sends entered obstacles with the single-route request and retains invalid bounds', async () => {
  const layout = { id: 5, project_id: 1, project_floor_id: 2, version_number: 3,
    geometry: { walls: [], symbols: [{ id: 'manual:1', class: { name: 'Outlet' }, position: { x: 2, y: 1 } }] } }
  routingRequest.mockResolvedValue({ version_number: 4 })
  render(<RoutingPanel layout={layout} onSaved={vi.fn()} />)
  for (const label of ['Panel x (m)', 'Panel y (m)', 'Panel elevation (m)', 'Service elevation (m)', 'Target elevation (m)']) {
    fireEvent.change(screen.getByLabelText(label), { target: { value: '3' } })
  }
  fireEvent.click(screen.getByRole('button', { name: 'Add route obstacle' }))
  for (const [key, value] of [['minimum x', '1'], ['minimum y', '2'], ['maximum x', '3'], ['maximum y', '4'], ['bottom elevation', '-1'], ['top elevation', '0']]) {
    fireEvent.change(screen.getByLabelText(`Route obstacle 1 ${key} (m)`), { target: { value } })
  }
  const form = screen.getByRole('button', { name: 'Calculate and save route' }).closest('form')
  fireEvent.submit(form)
  await screen.findByText('Route version 4 saved.')
  expect(routingRequest.mock.calls[0][1].configuration.obstacles).toEqual([
    { floor_id: 2, min_x: 1, min_y: 2, max_x: 3, max_y: 4, bottom: -1, top: 0 },
  ])
  routingRequest.mockClear()
  fireEvent.change(screen.getByLabelText('Route obstacle 1 top elevation (m)'), { target: { value: '-2' } })
  fireEvent.submit(form)
  const alert = await screen.findByRole('alert')
  await waitFor(() => expect(document.activeElement).toBe(alert))
  expect(routingRequest).not.toHaveBeenCalled()
  expect(screen.getByLabelText('Route obstacle 1 top elevation (m)').value).toBe('-2')
})

const obstacleLayout = { id: 5, project_id: 1, project_floor_id: 2, version_number: 3,
  geometry: { walls: [], symbols: [{ id: 'manual:1', class: { name: 'Outlet' }, position: { x: 2, y: 1 } }] } }
const obstacleRecord = { id: 8, version_number: 4, project_id: 1, stale: false, layout_versions: { 2: 5 },
  configuration: { floors: [{ floor_id: 2, expected_layout_version: 3, offset_x: 0, offset_y: 0 }], connectors: [],
    obstacles: [{ floor_id: 2, min_x: 1, min_y: 2, max_x: 3, max_y: 4, bottom: -1, top: 0 }] },
  result: { algorithm: 'orthogonal_astar_v1', total_meters: 7, horizontal_meters: 4, vertical_meters: 3 } }

it('restores saved single-route obstacles on reload and preserves edits across a stable refresh', async () => {
  routingRequest.mockResolvedValue(obstacleRecord)
  const rendered = render(<RoutingPanel layout={obstacleLayout} record={obstacleRecord} onSaved={vi.fn()} />)
  expect(screen.getByLabelText('Route obstacle 1 bottom elevation (m)').value).toBe('-1')
  fireEvent.change(screen.getByLabelText('Route obstacle 1 top elevation (m)'), { target: { value: '2' } })
  rendered.rerender(<RoutingPanel layout={{ ...obstacleLayout }} record={{ ...obstacleRecord }} onSaved={vi.fn()} />)
  expect(screen.getByLabelText('Route obstacle 1 top elevation (m)').value).toBe('2')
  for (const label of ['Panel x (m)', 'Panel y (m)', 'Panel elevation (m)', 'Service elevation (m)', 'Target elevation (m)']) {
    fireEvent.change(screen.getByLabelText(label), { target: { value: '3' } })
  }
  fireEvent.submit(screen.getByRole('button', { name: 'Calculate and save route' }).closest('form'))
  await screen.findByText('Route version 4 saved.')
  expect(routingRequest.mock.calls[0][1].configuration.obstacles).toEqual([{ ...obstacleRecord.configuration.obstacles[0], top: 2 }])
})

it.each([
  ['stale layout', { stale: true }],
  ['different layout', { layout_versions: { 2: 7 } }],
  ['different project', { project_id: 99 }],
  ['malformed barriers', { configuration: { ...obstacleRecord.configuration, obstacles: [{}] } }],
  ['underground configuration', { configuration: { ...obstacleRecord.configuration, installation_method: 'underground' } }],
])('blocks %s rather than silently replacing saved obstacles with empty background', (_reason, overrides) => {
  render(<RoutingPanel layout={obstacleLayout} record={{ ...obstacleRecord, ...overrides }} onSaved={vi.fn()} />)
  expect(screen.getByRole('alert').textContent).toContain('rather than dropping barriers')
  const button = screen.getByRole('button', { name: 'Calculate and save route' })
  fireEvent.submit(button.closest('form'))
  expect(routingRequest).not.toHaveBeenCalled()
})
