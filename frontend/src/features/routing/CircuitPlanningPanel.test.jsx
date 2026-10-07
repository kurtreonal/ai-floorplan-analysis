/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { CircuitPlanningPanel } from './CircuitPlanningPanel.jsx'
import { previewCircuit } from '../../api/routing.js'
vi.mock('../../api/routing.js', () => ({ previewCircuit: vi.fn() }))
vi.mock('../editor-2d/CanonicalLayoutCanvas.jsx', () => ({ CanonicalLayoutCanvas: ({ routeSegments }) => <div data-testid="circuit-2d">{JSON.stringify(routeSegments)}</div> }))
afterEach(() => { cleanup(); vi.clearAllMocks() })
const layout = { id: 5, project_id: 1, project_floor_id: 2, version_number: 3,
  geometry: { walls: [], symbols: [{ id: 'detected:1', class: { name: 'Troffer light' }, position: { x: 2, y: 1 } }] } }
const record = { project_id: 1, layout_versions: { 2: 5 }, configuration: { floors: [{ floor_id: 2, offset_x: 0, offset_y: 0 }] }, stale: false,
  result: { branches: [{ symbol_id: 'detected:1' }], total_meters: 1, horizontal_meters: 1, vertical_meters: 0,
    segments: [{ kind: 'ceiling_service', start: { floor_id: 2, x: 1, y: 1, elevation_meters: 3 }, end: { floor_id: 2, x: 2, y: 1, elevation_meters: 3 } }] } }
function fill() {
  fireEvent.click(screen.getByLabelText('Include Troffer light · detected:1'))
  for (const [label, value] of [['Circuit identifier', 'C-LGT'], ['Installation method', 'ceiling_service'],
    ['Circuit panel x (m)', '1'], ['Circuit panel y (m)', '1'], ['Circuit panel elevation (m)', '3'],
    ['Circuit service elevation (m)', '3'], ['Elevation for detected:1 (m)', '3']]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } })
  }
  fireEvent.click(screen.getByLabelText(/I confirm this circuit membership/))
  fireEvent.submit(screen.getByRole('button', { name: 'Preview shared circuit' }).closest('form'))
}
it('selects named saved devices with explicit heights, shares 2D coordinates and clears edited previews', async () => {
  previewCircuit.mockResolvedValue(record)
  const onPreview = vi.fn()
  render(<CircuitPlanningPanel layout={layout} onPreview={onPreview} />)
  expect(screen.getByRole('button', { name: 'Preview shared circuit' }).disabled).toBe(true)
  fill()
  await waitFor(() => expect(onPreview).toHaveBeenCalledWith(record))
  expect(previewCircuit.mock.calls[0][1]).toMatchObject({ circuit_id: 'C-LGT', installation_method: 'ceiling_service',
    targets: [{ symbol_id: 'detected:1', x: 2, y: 1, elevation_meters: 3 }], floors: [{ expected_layout_version: 3 }] })
  expect(screen.getByText(/Not saved; no estimate/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Compare circuit in 2D' }))
  expect(screen.getByTestId('circuit-2d').textContent).toContain('ceiling_service')
  fireEvent.change(screen.getByLabelText('Circuit service elevation (m)'), { target: { value: '4' } })
  expect(onPreview).toHaveBeenLastCalledWith(null)
  expect(screen.queryByTestId('circuit-2d')).toBeNull()
})
it('rejects a changed pinned snapshot and focuses the error without publishing preview geometry', async () => {
  previewCircuit.mockResolvedValue({ ...record, layout_versions: { 2: 8 } })
  const onPreview = vi.fn()
  render(<CircuitPlanningPanel layout={layout} onPreview={onPreview} />)
  fill()
  const alert = await screen.findByRole('alert')
  expect(alert.textContent).toContain('Layout changed')
  expect(document.activeElement).toBe(alert)
  expect(onPreview).not.toHaveBeenCalled()
})
it('aborts unmounted requests and fences a late response', async () => {
  let finish
  previewCircuit.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  const onPreview = vi.fn()
  const rendered = render(<CircuitPlanningPanel layout={layout} onPreview={onPreview} />)
  fill()
  await waitFor(() => expect(previewCircuit).toHaveBeenCalled())
  const signal = previewCircuit.mock.calls[0][2].signal
  rendered.unmount()
  expect(signal.aborted).toBe(true)
  finish(record)
  await Promise.resolve()
  expect(onPreview).not.toHaveBeenCalled()
})
