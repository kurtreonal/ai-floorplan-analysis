/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { CircuitPlanningPanel } from './CircuitPlanningPanel.jsx'
import { previewCircuit, saveCircuit } from '../../api/routing.js'
vi.mock('../../api/routing.js', () => ({ previewCircuit: vi.fn(), saveCircuit: vi.fn() }))
vi.mock('../editor-2d/CanonicalLayoutCanvas.jsx', () => ({ CanonicalLayoutCanvas: ({ routeSegments }) => <div data-testid="circuit-2d">{JSON.stringify(routeSegments)}</div> }))
afterEach(() => { cleanup(); vi.clearAllMocks() })
const layout = { id: 5, project_id: 1, project_floor_id: 2, version_number: 3,
  geometry: { floor: { elevation_meters: 0 }, walls: [], symbols: [{ id: 'detected:1', class: { name: 'Troffer light' }, position: { x: 2, y: 1 } }] } }
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
it('leaves conductor count unset by default and submits only an explicit uniform count',async()=>{
  const measured={...record,result:{...record.result,planning_takeoff:{conduit_meters:4,vertical_meters:1,
    conductor_count:3,one_conductor_meters:4,total_conductor_meters:12}}}
  previewCircuit.mockResolvedValue(measured)
  render(<CircuitPlanningPanel layout={layout} onPreview={vi.fn()} />)
  const input=screen.getByLabelText('Uniform conductors along selected network (optional)')
  expect(input.value).toBe('')
  fireEvent.change(input,{target:{value:'3'}})
  fill()
  await waitFor(()=>expect(previewCircuit).toHaveBeenCalled())
  expect(previewCircuit.mock.calls[0][1].conductor_count).toBe(3)
  expect(screen.getByRole('region',{name:'Selected network quantities'}).textContent).toContain('12.000 conductor-m')
})

it('requires explicit observed path selection and restores it without inventing circuit membership', async () => {
  const sourceLayout = { ...layout, geometry: { ...layout.geometry, routes: [{ id: 7, points: [] }, { id: 8, points: [] }] },
    extension: { route_details: [{ route_id: 7, route_kind: 'observed' }, { route_id: 8, route_kind: 'generated' }] } }
  previewCircuit.mockResolvedValue(record)
  const rendered = render(<CircuitPlanningPanel layout={sourceLayout} onPreview={vi.fn()} />)
  expect(screen.getByLabelText('Use observed route 7').checked).toBe(false)
  expect(screen.queryByLabelText('Use observed route 8')).toBeNull()
  fireEvent.click(screen.getByLabelText('Use observed route 7'))
  fill()
  await waitFor(() => expect(previewCircuit).toHaveBeenCalled())
  expect(previewCircuit.mock.calls[0][1].observed_route_assignments).toEqual([{ floor_id: 2, route_id: 7 }])
  const saved = savedCircuit()
  saved.configuration.observed_route_assignments = [{ floor_id: 2, route_id: 7 }]
  saved.configuration.routing_mode = 'missing_devices'
  saved.configuration.panel = { floor_id: 2, x: 1, y: 1, elevation_meters: 3 }
  saved.configuration.targets = [{ floor_id: 2, symbol_id: 'detected:1', x: 2, y: 1, elevation_meters: 3 }]
  rendered.rerender(<CircuitPlanningPanel layout={sourceLayout} record={saved} onPreview={vi.fn()} />)
  expect(screen.getByLabelText('Use observed route 7').checked).toBe(true)
  expect(screen.getByLabelText(/I confirm this circuit membership/).checked).toBe(false)
})

it('defers missing device elevations without inventing them or blocking other assignments', async () => {
  const second = { id: 'detected:2', class: { name: 'Outlet' }, position: { x: 3, y: 1 } }
  previewCircuit.mockResolvedValue(record)
  render(<CircuitPlanningPanel layout={{ ...layout, geometry: { ...layout.geometry, symbols: [...layout.geometry.symbols, second] } }} onPreview={vi.fn()} />)
  fireEvent.click(screen.getByLabelText('Include Outlet · detected:2'))
  fill()
  await waitFor(() => expect(previewCircuit).toHaveBeenCalled())
  expect(previewCircuit.mock.calls[0][1].targets.map((target) => target.symbol_id)).toEqual(['detected:1'])
  expect(screen.getByText(/Mounting elevation still needed: detected:2/)).toBeTruthy()
})

it('sends underground planning only with entered depth and explicit floor passages, then restores those inputs', async () => {
  previewCircuit.mockResolvedValue(record)
  const onPreview = vi.fn()
  const rendered = render(<CircuitPlanningPanel layout={wallLayout} onPreview={onPreview} />)
  fireEvent.click(screen.getByLabelText('Include Troffer light · detected:1'))
  for (const [label, value] of [['Circuit identifier', 'C-POWER'], ['Installation method', 'underground'],
    ['Circuit panel x (m)', '1'], ['Circuit panel y (m)', '1'], ['Circuit panel elevation (m)', '1.4'],
    ['Circuit service elevation (m)', '-0.4'], ['Elevation for detected:1 (m)', '1.2'],
    ['Circuit panel wall', '7'], ['Wall for detected:1', '7']]) fireEvent.change(screen.getByLabelText(label), { target: { value } })
  expect(screen.getByText(/below this saved floor \(0 m\)/)).toBeTruthy()
  fireEvent.click(screen.getByLabelText(/Use floor passages at the entered/))
  fireEvent.click(screen.getByLabelText(/I confirm this circuit membership/))
  fireEvent.submit(screen.getByRole('button', { name: 'Preview shared circuit' }).closest('form'))
  await waitFor(() => expect(previewCircuit).toHaveBeenCalled())
  expect(previewCircuit.mock.calls[0][1]).toMatchObject({ installation_method: 'underground', floor_passages_confirmed: true,
    floors: [{ service_elevation_meters: -.4 }], panel: { elevation_meters: 1.4, wall_id: 7 },
    targets: [{ elevation_meters: 1.2, wall_id: 7 }] })
  const saved = savedCircuit()
  saved.configuration = { ...saved.configuration, installation_method: 'underground', floor_passages_confirmed: true,
    floors: [{ ...saved.configuration.floors[0], service_elevation_meters: -.4 }] }
  rendered.rerender(<CircuitPlanningPanel layout={wallLayout} record={saved} onPreview={onPreview} />)
  expect(screen.getByLabelText('Installation method').value).toBe('underground')
  expect(screen.getByLabelText('Circuit service elevation (m)').value).toBe('-0.4')
  expect(screen.getByLabelText(/Use floor passages at the entered/).checked).toBe(true)
  expect(screen.getByLabelText(/I confirm this circuit membership/).checked).toBe(false)
})
it('selects named saved devices with explicit heights, shares 2D coordinates and clears edited previews', async () => {
  previewCircuit.mockResolvedValue(record)
  const onPreview = vi.fn()
  render(<CircuitPlanningPanel layout={layout} onPreview={onPreview} />)
  expect(screen.getByRole('button', { name: 'Preview shared circuit' }).disabled).toBe(true)
  fill()
  await waitFor(() => expect(onPreview).toHaveBeenCalledWith(record))
  expect(previewCircuit.mock.calls[0][1]).toMatchObject({ circuit_id: 'C-LGT', installation_method: 'ceiling_service',
    routing_mode: 'missing_devices',
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
  await waitFor(() => expect(document.activeElement).toBe(alert))
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

it('saves a preview and retries an uncertain response with the identical request identity', async () => {
  previewCircuit.mockResolvedValue(record)
  const saved = { ...record, id: 9, version_number: 2, result: { ...record.result, status: 'saved_planning' } }
  saveCircuit.mockRejectedValueOnce(new Error('Connection lost')).mockResolvedValueOnce(saved)
  const onPreview = vi.fn(), onSaved = vi.fn()
  render(<CircuitPlanningPanel layout={layout} record={{ version_number: 1, result: {} }} onPreview={onPreview} onSaved={onSaved} />)
  fill()
  const button = await screen.findByRole('button', { name: 'Save planning circuit' })
  fireEvent.click(button)
  await screen.findByText('Connection lost')
  const payload = saveCircuit.mock.calls[0][1]
  expect(payload).toMatchObject({ intent: 'save_planning_circuit', expected_route_version: 1 })
  expect(payload.request_id).toMatch(/^[0-9a-f-]{36}$/)
  fireEvent.click(button)
  await waitFor(() => expect(onSaved).toHaveBeenCalledWith(saved))
  expect(saveCircuit.mock.calls[1][1]).toEqual(payload)
  expect(onPreview).toHaveBeenLastCalledWith(null)
})

function savedCircuit(overrides = {}) {
  return { ...record, id: 9, version_number: 2,
    configuration: { circuit_id: 'C-SAVED', installation_method: 'ceiling_service',
      floors: [{ floor_id: 2, expected_layout_version: 3, service_elevation_meters: 3.2, offset_x: 0, offset_y: 0 }],
      panel: { floor_id: 2, x: 0.8, y: 1.1, elevation_meters: 1.4, wall_id: 7 },
      targets: [{ floor_id: 2, symbol_id: 'detected:1', x: 2, y: 1, elevation_meters: 2.8, wall_id: 7 }],
      connectors: [], obstacles: [], grid_step_meters: 0.4, alignment_confirmed: true, purpose: 'planning' },
    result: { ...record.result, status: 'saved_planning', circuit_id: 'C-SAVED' }, ...overrides }
}
const wallLayout = { ...layout, geometry: { ...layout.geometry, walls: [{ id: 7, status: 'verified' }] } }

it('restores saved membership and entered values after reload without reconfirming or resetting edited values', async () => {
  const saved = savedCircuit(), onPreview = vi.fn(), onSaved = vi.fn()
  const rendered = render(<CircuitPlanningPanel layout={wallLayout} onPreview={onPreview} onSaved={onSaved} />)
  rendered.rerender(<CircuitPlanningPanel layout={wallLayout} record={saved} onPreview={onPreview} onSaved={onSaved} />)
  expect(screen.getByLabelText('Include Troffer light · detected:1').checked).toBe(true)
  for (const [label, value] of [['Circuit identifier', 'C-SAVED'], ['Installation method', 'ceiling_service'],
    ['Circuit panel x (m)', '0.8'], ['Circuit panel y (m)', '1.1'], ['Circuit panel elevation (m)', '1.4'],
    ['Circuit service elevation (m)', '3.2'], ['Elevation for detected:1 (m)', '2.8'],
    ['Circuit panel wall', '7'], ['Wall for detected:1', '7'], ['Circuit graph spacing (m)', '0.4']]) {
    expect(screen.getByLabelText(label).value).toBe(value)
  }
  expect(screen.getByLabelText(/I confirm this circuit membership/).checked).toBe(false)
  fireEvent.change(screen.getByLabelText('Circuit service elevation (m)'), { target: { value: '3.5' } })
  rendered.rerender(<CircuitPlanningPanel layout={{ ...wallLayout }} record={{ ...saved }} onPreview={onPreview} onSaved={onSaved} />)
  expect(screen.getByLabelText('Circuit service elevation (m)').value).toBe('3.5')
  previewCircuit.mockResolvedValue(record)
  fireEvent.click(screen.getByLabelText(/I confirm this circuit membership/))
  fireEvent.submit(screen.getByRole('button', { name: 'Preview shared circuit' }).closest('form'))
  await waitFor(() => expect(previewCircuit).toHaveBeenCalled())
  expect(previewCircuit.mock.calls[0][1]).toMatchObject({ circuit_id: 'C-SAVED',
    floors: [{ service_elevation_meters: 3.5 }], panel: saved.configuration.panel,
    targets: saved.configuration.targets, grid_step_meters: 0.4 })
})

it.each([
  ['stale', { stale: true }],
  ['another layout', { layout_versions: { 2: 6 } }],
  ['another project', { project_id: 99 }],
  ['changed device coordinates', { configuration: { ...savedCircuit().configuration,
    targets: [{ ...savedCircuit().configuration.targets[0], x: 3 }] } }],
  ['uneditable obstacle configuration', { configuration: { ...savedCircuit().configuration, obstacles: [{}] } }],
])('leaves fields empty for a saved circuit with %s', (_reason, overrides) => {
  render(<CircuitPlanningPanel layout={wallLayout} record={savedCircuit(overrides)} onPreview={vi.fn()} />)
  expect(screen.getByLabelText('Circuit identifier').value).toBe('')
  expect(screen.getByLabelText('Circuit service elevation (m)').value).toBe('')
  expect(screen.getByLabelText('Include Troffer light · detected:1').checked).toBe(false)
  expect(screen.getByText(/Saved circuit inputs do not match/)).toBeTruthy()
})

it('aborts work when the layout changes and fences its late preview response', async () => {
  let finish
  previewCircuit.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  const onPreview = vi.fn()
  const rendered = render(<CircuitPlanningPanel layout={layout} onPreview={onPreview} />)
  fill()
  await waitFor(() => expect(previewCircuit).toHaveBeenCalled())
  const signal = previewCircuit.mock.calls[0][2].signal
  rendered.rerender(<CircuitPlanningPanel layout={{ ...layout, id: 6, version_number: 4 }} onPreview={onPreview} />)
  expect(signal.aborted).toBe(true)
  expect(screen.getByLabelText('Circuit identifier').value).toBe('')
  finish(record)
  await Promise.resolve()
  expect(onPreview).not.toHaveBeenCalled()
})

it('clears a published preview when its layout changes', async () => {
  previewCircuit.mockResolvedValue(record)
  const onPreview = vi.fn()
  const rendered = render(<CircuitPlanningPanel layout={layout} onPreview={onPreview} />)
  fill()
  await waitFor(() => expect(onPreview).toHaveBeenCalledWith(record))
  rendered.rerender(<CircuitPlanningPanel layout={{ ...layout, id: 6, version_number: 4 }} onPreview={onPreview} />)
  expect(onPreview).toHaveBeenLastCalledWith(null)
})

const reviewedObstacle = { floor_id: 2, min_x: 1, min_y: 2, max_x: 3, max_y: 4, bottom: -1, top: 1 }

it('restores explicit obstacle bounds and preserves them through preview and save', async () => {
  const saved = savedCircuit()
  saved.configuration.obstacles = [reviewedObstacle]
  previewCircuit.mockImplementation(async (_projectId, configuration) => ({ ...record, configuration }))
  saveCircuit.mockResolvedValue(saved)
  const onPreview = vi.fn(), onSaved = vi.fn()
  const rendered = render(<CircuitPlanningPanel layout={wallLayout} record={saved} onPreview={onPreview} onSaved={onSaved} />)
  expect(screen.getByLabelText('Circuit obstacle 1 minimum x (m)').value).toBe('1')
  expect(screen.getByLabelText('Circuit obstacle 1 bottom elevation (m)').value).toBe('-1')
  fireEvent.change(screen.getByLabelText('Circuit obstacle 1 top elevation (m)'), { target: { value: '2' } })
  rendered.rerender(<CircuitPlanningPanel layout={{ ...wallLayout }} record={{ ...saved }} onPreview={onPreview} onSaved={onSaved} />)
  expect(screen.getByLabelText('Circuit obstacle 1 top elevation (m)').value).toBe('2')
  fireEvent.click(screen.getByLabelText(/I confirm this circuit membership/))
  fireEvent.submit(screen.getByRole('button', { name: 'Preview shared circuit' }).closest('form'))
  await waitFor(() => expect(previewCircuit).toHaveBeenCalled())
  expect(previewCircuit.mock.calls[0][1].obstacles).toEqual([{ ...reviewedObstacle, top: 2 }])
  fireEvent.click(await screen.findByRole('button', { name: 'Save planning circuit' }))
  await waitFor(() => expect(onSaved).toHaveBeenCalledWith(saved))
  expect(saveCircuit.mock.calls[0][1].obstacles).toEqual([{ ...reviewedObstacle, top: 2 }])
})

it.each(['add', 'remove'])('invalidates published circuit preview when obstacles %s', async (action) => {
  const saved = savedCircuit()
  saved.configuration.obstacles = [reviewedObstacle]
  previewCircuit.mockResolvedValue(record)
  const onPreview = vi.fn()
  render(<CircuitPlanningPanel layout={wallLayout} record={saved} onPreview={onPreview} />)
  fireEvent.click(screen.getByLabelText(/I confirm this circuit membership/))
  fireEvent.submit(screen.getByRole('button', { name: 'Preview shared circuit' }).closest('form'))
  await waitFor(() => expect(onPreview).toHaveBeenCalledWith(record))
  fireEvent.click(screen.getByRole('button', { name: action === 'add' ? 'Add circuit obstacle' : 'Remove circuit obstacle 1' }))
  expect(onPreview).toHaveBeenLastCalledWith(null)
  expect(screen.queryByRole('button', { name: 'Save planning circuit' })).toBeNull()
})

it('rejects reversed obstacle bounds without dropping the obstacle or calling inference', async () => {
  const saved = savedCircuit()
  saved.configuration.obstacles = [reviewedObstacle]
  render(<CircuitPlanningPanel layout={wallLayout} record={saved} onPreview={vi.fn()} />)
  fireEvent.change(screen.getByLabelText('Circuit obstacle 1 minimum x (m)'), { target: { value: '5' } })
  fireEvent.click(screen.getByLabelText(/I confirm this circuit membership/))
  fireEvent.submit(screen.getByRole('button', { name: 'Preview shared circuit' }).closest('form'))
  expect(await screen.findByRole('alert')).toBeTruthy()
  expect(previewCircuit).not.toHaveBeenCalled()
  expect(screen.getByLabelText('Circuit obstacle 1 minimum x (m)').value).toBe('5')
})
