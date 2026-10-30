/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { importTrainedLegends, importApprovedPdfLegends, listAdminLegends, saveAdminLegend } from '../../api/adminLegends.js'
import { AdminLegendPanel } from './AdminLegendPanel.jsx'
vi.mock('../../api/adminLegends.js', () => ({listAdminLegends:vi.fn(), saveAdminLegend:vi.fn(), importTrainedLegends:vi.fn(), importApprovedPdfLegends:vi.fn()}))
afterEach(() => { cleanup(); vi.resetAllMocks() })

it('shows one catalog meaning with recoverable source aliases, without deleting or saving on load', async () => {
  listAdminLegends.mockResolvedValue([
    { id: 1, class_id: 0, name: 'Panelboard [sheet-10:L04]', is_active: true },
    { id: 2, class_id: 1, name: 'Panelboard [sheet-13:L04]', is_active: true },
  ])
  render(<AdminLegendPanel />)
  fireEvent.click(screen.getByText('Manage legends'))
  await screen.findByText('Panelboard')
  expect(screen.getAllByText('Manage duplicates (2)')).toHaveLength(1)
  expect(screen.getAllByText('Deactivate')).toHaveLength(2)
  expect(screen.queryByText(/sheet-13/)).toBeNull()
  expect(saveAdminLegend).not.toHaveBeenCalled()
})

it('imports all approved PDF definitions independently of trained weights, only on admin action', async () => {
  listAdminLegends.mockResolvedValue([])
  importApprovedPdfLegends.mockResolvedValue(Array.from({ length: 40 }, (_, i) => ({ id: i + 1 })))
  render(<AdminLegendPanel />)
  fireEvent.click(screen.getByText('Manage legends'))
  await waitFor(() => expect(screen.getByText('Import approved drawing legends').disabled).toBe(false))
  expect(importApprovedPdfLegends).not.toHaveBeenCalled()
  fireEvent.click(screen.getByText('Import approved drawing legends'))
  await screen.findByText(/40 approved PDF legend entries registered: 36 symbols\/notations and 4 wiring patterns/)
  expect(importApprovedPdfLegends).toHaveBeenCalledTimes(1)
  expect(importTrainedLegends).not.toHaveBeenCalled()
  expect(saveAdminLegend).not.toHaveBeenCalled()
})

it('imports only on explicit action and reloads without approving detections', async () => {
  listAdminLegends.mockResolvedValue([])
  importTrainedLegends.mockResolvedValue(Array.from({ length: 56 }, (_, i) => ({ id: i + 1 })))
  render(<AdminLegendPanel />)
  fireEvent.click(screen.getByText('Manage legends'))
  await waitFor(() => expect(screen.getByText('Import trained legends').disabled).toBe(false))
  expect(importTrainedLegends).not.toHaveBeenCalled()
  fireEvent.click(screen.getByText('Import trained legends'))
  await screen.findByText(/56 trained legend entries registered with their drawing identities/)
  expect(importTrainedLegends).toHaveBeenCalledTimes(1)
  expect(listAdminLegends).toHaveBeenCalledTimes(2)
  expect(saveAdminLegend).not.toHaveBeenCalled()
})

it('loads only when opened and saves an explicit legend, without creating on mount', async () => {
  listAdminLegends.mockResolvedValue([])
  saveAdminLegend.mockResolvedValue({id:1,class_id:0,name:'Test outlet',is_active:true})
  render(<AdminLegendPanel />)
  expect(listAdminLegends).not.toHaveBeenCalled()
  fireEvent.click(screen.getByText('Manage legends'))
  await waitFor(() => expect(screen.getByText('Add device').disabled).toBe(false))
  fireEvent.click(screen.getByText('Add device'))
  await waitFor(() => expect(screen.getByLabelText('Legend name').disabled).toBe(false))
  expect(saveAdminLegend).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText('Legend name'), {target:{value:'Test outlet'}})
  fireEvent.click(screen.getByText('Add active legend'))
  await screen.findByText('Test outlet saved.')
  expect(saveAdminLegend).toHaveBeenCalledWith({class_id:0,name:'Test outlet',is_active:true}, undefined)
})

it('requires a catalog reload after an uncertain save instead of blindly retrying', async () => {
  listAdminLegends.mockResolvedValue([{id:2,class_id:1,name:'Test switch',is_active:true}])
  saveAdminLegend.mockRejectedValue(new Error('Connection interrupted'))
  render(<AdminLegendPanel />)
  fireEvent.click(screen.getByText('Manage legends'))
  fireEvent.click(await screen.findByText('Deactivate'))
  await screen.findByRole('alert')
  expect(screen.getByText('Add device').disabled).toBe(true)
  expect(saveAdminLegend).toHaveBeenCalledTimes(1)
})
