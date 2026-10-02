/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createEstimate, EstimateApiError, fetchEstimateOptions, listEstimates } from '../../api/estimates.js'
import { EstimatePage } from './EstimatePage.jsx'

vi.mock('../../api/estimates.js', async () => ({ ...await vi.importActual('../../api/estimates.js'), createEstimate: vi.fn(), fetchEstimateOptions: vi.fn(), listEstimates: vi.fn() }))
const designer = { user: { role: 'DESIGNER' } }
const record = { id: 4, project_id: 15, version_number: 2, currency: 'PHP', total: '1234.56', items: [{ line_number: 1, material_id: 5, material_name: 'Reviewed fixture', material_code: 'L5', unit: 'piece', quantity: '2', captured_unit_price: '50', line_total: '100' }] }
const options = { route_version_id: 11, stale: false, floors: [2], components: [{ class_id: 7, class_name: 'Troffer', quantity: 2 }], materials: [{ id: 5, name: 'Fixture', code: 'L5', unit: 'piece', has_price: true }, { id: 6, name: 'Conduit', code: 'C6', unit: 'meter', has_price: true }, { id: 7, name: 'Wire', code: 'W7', unit: 'meter', has_price: true }, { id: 8, name: 'Unpriced material', unit: 'piece', has_price: false }] }
beforeEach(() => { listEstimates.mockResolvedValue([]); fetchEstimateOptions.mockResolvedValue(options) })
afterEach(() => { cleanup(); vi.resetAllMocks() })

async function fillMappings() {
  await screen.findByLabelText('Material for Troffer')
  fireEvent.change(screen.getByLabelText('Material for Troffer'), { target: { value: '5' } })
  fireEvent.change(screen.getByLabelText('Material units per Troffer'), { target: { value: '1' } })
  fireEvent.change(screen.getByLabelText('Conduit material (meter)'), { target: { value: '6' } })
  fireEvent.change(screen.getByLabelText('Wire material (meter)'), { target: { value: '7' } })
  fireEvent.change(screen.getByLabelText('Conductor count'), { target: { value: '3' } })
  fireEvent.click(screen.getByLabelText('I reviewed these material mappings and conversion factors.'))
}

it('shows captured backend totals rather than recalculating them from line items', async () => {
  listEstimates.mockResolvedValue([record])
  fetchEstimateOptions.mockRejectedValue(new EstimateApiError(503))
  render(<EstimatePage projectId={15} session={designer} />)
  await screen.findByText('Reviewed fixture')
  expect(screen.getAllByText(/1,234\.56/).length).toBeGreaterThan(0)
  expect(screen.getByText(/The estimate service is unavailable/)).toBeTruthy()
  expect(screen.getByText(/Later material-price updates do not alter/)).toBeTruthy()
})

it('does not expose generation to Admin or imply missing routes are ready', async () => {
  fetchEstimateOptions.mockResolvedValue({ ...options, route_version_id: null })
  render(<EstimatePage projectId={15} session={{ user: { role: 'ADMIN' } }} />)
  expect(await screen.findByText('No saved estimates yet.')).toBeTruthy()
  expect(screen.getByText('Admin read-only view. A Designer generates estimates.')).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Generate estimate snapshot' })).toBeNull()
  expect(screen.getByText('Needs review')).toBeTruthy()
})

it('requires explicit mappings and sends only reviewed inputs to the existing API', async () => {
  createEstimate.mockResolvedValue(record)
  render(<EstimatePage projectId={15} session={designer} />)
  await fillMappings()
  expect(screen.queryByRole('option', { name: /Unpriced material/ })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Generate estimate snapshot' }))
  await screen.findByText('Reviewed fixture')
  expect(createEstimate).toHaveBeenCalledWith(15, expect.objectContaining({ request_id: expect.any(String), route_version_id: 11, components: [{ class_id: 7, material_id: 5, units_per_symbol: '1' }], conduit_material_id: 6, wire_material_id: 7, conductor_count: 3, mappings_confirmed: true }), expect.objectContaining({ signal: expect.any(AbortSignal) }))
})

it('locks uncertain inputs and retries exactly the same request identity and payload', async () => {
  createEstimate.mockRejectedValueOnce(new EstimateApiError(503)).mockResolvedValueOnce(record)
  render(<EstimatePage projectId={15} session={designer} />)
  await fillMappings()
  fireEvent.click(screen.getByRole('button', { name: 'Generate estimate snapshot' }))
  const retry = await screen.findByRole('button', { name: 'Retry identical snapshot request' })
  expect(screen.getByRole('button', { name: 'Reload inputs' }).disabled).toBe(true)
  expect(screen.getByLabelText('Material for Troffer').closest('fieldset').disabled).toBe(true)
  const originalPayload = createEstimate.mock.calls[0][1]
  fireEvent.click(retry)
  await screen.findByText('Reviewed fixture')
  expect(createEstimate.mock.calls[1][1]).toEqual(originalPayload)
})

it('handles stale sources safely and refreshes readiness without hiding history', async () => {
  listEstimates.mockResolvedValue([record])
  fetchEstimateOptions.mockResolvedValueOnce({ ...options, stale: true }).mockResolvedValueOnce(options)
  render(<EstimatePage projectId={15} session={designer} />)
  await screen.findByText('Reviewed fixture')
  expect(screen.queryByRole('button', { name: 'Generate estimate snapshot' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Reload inputs' }))
  await screen.findByRole('button', { name: 'Generate estimate snapshot' })
  await waitFor(() => expect(fetchEstimateOptions).toHaveBeenCalledTimes(2))
})
