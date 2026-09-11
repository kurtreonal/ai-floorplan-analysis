/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { listAdminLegends, saveAdminLegend } from '../../api/adminLegends.js'
import { AdminLegendPanel } from './AdminLegendPanel.jsx'
vi.mock('../../api/adminLegends.js', () => ({listAdminLegends:vi.fn(), saveAdminLegend:vi.fn()}))
afterEach(() => { cleanup(); vi.resetAllMocks() })

it('loads only when opened and saves an explicit legend, without creating on mount', async () => {
  listAdminLegends.mockResolvedValue([])
  saveAdminLegend.mockResolvedValue({id:1,class_id:0,name:'Test outlet',is_active:true})
  render(<AdminLegendPanel />)
  expect(listAdminLegends).not.toHaveBeenCalled()
  fireEvent.click(screen.getByText('Manage symbol legends'))
  await waitFor(() => expect(screen.getByLabelText('Legend name').disabled).toBe(false))
  expect(saveAdminLegend).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText('Class number'), {target:{value:'0'}})
  fireEvent.change(screen.getByLabelText('Legend name'), {target:{value:'Test outlet'}})
  fireEvent.click(screen.getByText('Add active legend'))
  await screen.findByText('Test outlet: active.')
  expect(saveAdminLegend).toHaveBeenCalledWith({class_id:0,name:'Test outlet',is_active:true}, undefined)
})

it('requires a catalog reload after an uncertain save instead of blindly retrying', async () => {
  listAdminLegends.mockResolvedValue([{id:2,class_id:1,name:'Test switch',is_active:true}])
  saveAdminLegend.mockRejectedValue(new Error('Connection interrupted'))
  render(<AdminLegendPanel />)
  fireEvent.click(screen.getByText('Manage symbol legends'))
  fireEvent.click(await screen.findByText('Deactivate Test switch'))
  await screen.findByRole('alert')
  expect(screen.getByText('Add active legend').disabled).toBe(true)
  expect(saveAdminLegend).toHaveBeenCalledTimes(1)
})
