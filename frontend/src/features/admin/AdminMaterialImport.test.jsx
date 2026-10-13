/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { importMaterialPrices } from '../../api/materialPrices.js'
import { AdminMaterialImport } from './AdminMaterialImport.jsx'

vi.mock('../../api/materialPrices.js', () => ({ importMaterialPrices: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks() })
const preview = { file_sha256: 'a'.repeat(64), issues: [{ row_id: 'Wire:4', reason: 'TBA' }], rows: [
  { row_id: 'Wire:3', name: 'Cable', code: 'W1', unit: 'roll', unit_price: '100', current_price: null, version: 0, eligible: true },
  { row_id: 'Wire:5', name: 'Different identity', code: 'W2', unit: 'meter', unit_price: '5', current_price: '4', current_currency: 'PHP', version: 2, eligible: false, reason: 'Unit differs' },
] }
it('previews without applying, requires review and preserves versions/units when applying', async () => {
  importMaterialPrices.mockResolvedValueOnce(preview).mockResolvedValueOnce({ created: 1, updated: 1, unchanged: 0 })
  render(<AdminMaterialImport />)
  const file = new File(['fixture'], 'prices.xlsx')
  fireEvent.change(screen.getByLabelText('Price workbook (.xlsx)'), { target: { files: [file] } })
  fireEvent.click(screen.getByText('Preview prices'))
  await screen.findByText('Cable')
  expect(importMaterialPrices.mock.calls[0][1]).toBeNull()
  expect(screen.getByLabelText('Import Wire:5').disabled).toBe(true)
  expect(screen.getByText('Apply selected prices').disabled).toBe(true)
  fireEvent.click(screen.getByLabelText('I reviewed the selected prices, currency and purchase units.'))
  fireEvent.click(screen.getByText('Apply selected prices'))
  await screen.findByText(/1 new materials, 1 price revisions/)
  expect(importMaterialPrices.mock.calls[1][1]).toEqual({ file_sha256: 'a'.repeat(64), currency: 'PHP', expected_versions: { 'Wire:3': 0 }, confirmed: true })
})
it('clears an uncertain apply and requires a fresh preview', async () => {
  importMaterialPrices.mockResolvedValueOnce(preview).mockRejectedValueOnce(new Error('Unavailable'))
  render(<AdminMaterialImport />)
  fireEvent.change(screen.getByLabelText('Price workbook (.xlsx)'), { target: { files: [new File([''], 'p.xlsx')] } })
  fireEvent.click(screen.getByText('Preview prices')); await screen.findByText('Cable')
  fireEvent.click(screen.getByLabelText('I reviewed the selected prices, currency and purchase units.'))
  fireEvent.click(screen.getByText('Apply selected prices'))
  await screen.findByRole('alert')
  await waitFor(() => expect(screen.queryByText('Apply selected prices')).toBeNull())
})
