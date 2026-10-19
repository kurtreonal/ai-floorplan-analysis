/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ClientPricingPanel } from './ClientPricingPanel.jsx'
import { applyProjectPrices, fetchProjectPrice, inspectProjectPrices, listProjectPrices, previewProjectPrices, ProjectPricingError } from '../../api/projectPricing.js'
vi.mock('../../api/projectPricing.js', async () => ({ ...await vi.importActual('../../api/projectPricing.js'),
  applyProjectPrices: vi.fn(), fetchProjectPrice: vi.fn(), inspectProjectPrices: vi.fn(), listProjectPrices: vi.fn(), previewProjectPrices: vi.fn() }))
const version = { id: 7, project_id: 15, version_number: 1, filename: 'client.csv', kind: 'client_bom' }
const row = { row_id: 'CSV:2', name: 'Client lamp', code: 'L1', specification: 'Explicit spec', unit: 'piece',
  unit_price: '4', currency: 'PHP', client_quantity: '9', reasons: ['Select a material.'], catalog_code: 'M1' }
const proposal = { file_sha256: 'a'.repeat(64), preview_token: 'b'.repeat(64), expected_version: 0,
  ready: false, document: { rows: [row] }, materials: [{ id: 5, name: 'Lamp', code: 'M1', unit: 'piece' }] }
beforeEach(() => {
  listProjectPrices.mockResolvedValue([])
  inspectProjectPrices.mockResolvedValue({ sheet: 'CSV', sheets: ['CSV'], header_row: 1,
    columns: [{ id: 'A', label: 'Description' }, { id: 'B', label: 'Unit' }, { id: 'C', label: 'Price' }, { id: 'D', label: 'Quantity' }] })
  previewProjectPrices.mockResolvedValue(proposal)
  applyProjectPrices.mockResolvedValue(version)
  fetchProjectPrice.mockResolvedValue({ ...version, document: { rows: [row] } })
})
afterEach(() => { cleanup(); vi.resetAllMocks() })

async function mapAndPreview() {
  fireEvent.click(screen.getByText('Import XLSX or CSV'))
  fireEvent.change(screen.getByLabelText('Client file'), { target: { files: [new File(['source'], 'client.csv')] } })
  fireEvent.change(screen.getByLabelText('Import type'), { target: { value: 'client_bom' } })
  fireEvent.click(screen.getByRole('button', { name: 'Read headers' }))
  await screen.findByLabelText('Description column')
  for (const [label, value] of [['Description column','A'], ['Purchase unit column','B'], ['Unit price column','C'], ['Client quantity column','D']])
    fireEvent.change(screen.getByLabelText(label), { target: { value } })
  fireEvent.change(screen.getByLabelText('Import currency'), { target: { value: 'PHP' } })
  fireEvent.click(screen.getByRole('button', { name: 'Preview rows' }))
  await screen.findByLabelText('Material for CSV:2')
}

async function validateMappings() {
  fireEvent.change(screen.getByLabelText('Material for CSV:2'), { target: { value: '5' } })
  previewProjectPrices.mockResolvedValue({ ...proposal, ready: true, document: { rows: [{ ...row, reasons: [], material_id: 5, units_per_purchase: '1' }] } })
  fireEvent.click(screen.getByRole('button', { name: 'Validate mappings' }))
  await screen.findByText('Mappings validated.')
  fireEvent.click(screen.getByLabelText('I reviewed these project prices, units, conversions and exclusions.'))
}

it('requires explicit column/material choices, validation and confirmation before saving', async () => {
  render(<ClientPricingPanel projectId={15} designer />)
  await mapAndPreview()
  expect(screen.getByLabelText('Material for CSV:2').value).toBe('')
  expect(screen.getByRole('button', { name: 'Save project import' }).disabled).toBe(true)
  await validateMappings()
  expect(applyProjectPrices).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Save project import' }))
  await screen.findByRole('status')
  const payload = applyProjectPrices.mock.calls[0][2]
  expect(payload).toMatchObject({ confirmed: true, file_sha256: proposal.file_sha256, preview_token: proposal.preview_token,
    expected_version: 0, mapping: { kind: 'client_bom', currency: 'PHP', columns: { quantity: 'D' } },
    choices: [{ row_id: 'CSV:2', material_id: 5 }] })
  expect(fetchProjectPrice).toHaveBeenCalledWith(15, '7', expect.objectContaining({ estimateId: undefined }))
})

it('invalidates a validated preview when a mapping/exclusion changes', async () => {
  render(<ClientPricingPanel projectId={15} designer />)
  await mapAndPreview(); await validateMappings()
  fireEvent.click(screen.getByLabelText('Exclude CSV:2'))
  expect(screen.getByRole('button', { name: 'Save project import' }).disabled).toBe(true)
  expect(screen.queryByLabelText('I reviewed these project prices, units, conversions and exclusions.')).toBeNull()
  expect(applyProjectPrices).not.toHaveBeenCalled()
})

it('locks uncertain imports and retries exactly the same request ID and source', async () => {
  applyProjectPrices.mockRejectedValueOnce(new ProjectPricingError(503)).mockResolvedValueOnce(version)
  render(<ClientPricingPanel projectId={15} designer />)
  await mapAndPreview(); await validateMappings()
  fireEvent.click(screen.getByRole('button', { name: 'Save project import' }))
  const retry = await screen.findByRole('button', { name: 'Retry identical import' })
  expect(screen.getByLabelText('Client file').closest('fieldset').disabled).toBe(true)
  const first = applyProjectPrices.mock.calls[0]
  fireEvent.click(retry)
  await screen.findByRole('status')
  expect(applyProjectPrices.mock.calls[1].slice(0,3)).toEqual(first.slice(0,3))
})

it('keeps client and calculated quantities separate in read-only history', async () => {
  listProjectPrices.mockResolvedValue([version])
  fetchProjectPrice.mockResolvedValue({ ...version, document: { rows: [row] },
    comparison: [{ row_id: 'CSV:2', client_quantity: '9', calculated_quantity: '2', difference: '-7', unit: 'piece' }] })
  render(<ClientPricingPanel projectId={15} designer={false} estimateId={12} />)
  fireEvent.change(await screen.findByLabelText('Saved client import'), { target: { value: '7' } })
  expect(await screen.findByText('-7')).toBeTruthy()
  expect(screen.getByText('9')).toBeTruthy()
  expect(screen.getByText('2 piece')).toBeTruthy()
  expect(screen.queryByText('Import XLSX or CSV')).toBeNull()
  expect(applyProjectPrices).not.toHaveBeenCalled()
})

it('drops comparison data as soon as the selected estimate changes and fences stale responses', async () => {
  listProjectPrices.mockResolvedValue([version])
  const { rerender } = render(<ClientPricingPanel projectId={15} designer={false} estimateId={12} />)
  fireEvent.change(await screen.findByLabelText('Saved client import'), { target: { value: '7' } })
  await screen.findByText('Client lamp')
  fetchProjectPrice.mockReturnValue(new Promise(() => {}))
  rerender(<ClientPricingPanel projectId={15} designer={false} estimateId={13} />)
  expect(screen.queryByText('Client lamp')).toBeNull()
  await waitFor(() => expect(fetchProjectPrice).toHaveBeenLastCalledWith(15, '7', expect.objectContaining({ estimateId: 13 })))
})
