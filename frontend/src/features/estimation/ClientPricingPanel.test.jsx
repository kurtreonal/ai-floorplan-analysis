/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ClientPricingPanel } from './ClientPricingPanel.jsx'
import { applyProjectPrices, fetchProjectPrice, listProjectPrices, previewProjectPrices, ProjectPricingError } from '../../api/projectPricing.js'
vi.mock('../../api/projectPricing.js', async () => ({ ...await vi.importActual('../../api/projectPricing.js'),
  applyProjectPrices: vi.fn(), fetchProjectPrice: vi.fn(), listProjectPrices: vi.fn(), previewProjectPrices: vi.fn() }))
const version = { id: 7, project_id: 15, version_number: 1, filename: 'client.csv', kind: 'client_bom' }
const row = { row_id: 'CSV:2', name: 'Client lamp', code: 'L1', specification: 'Explicit spec', unit: 'piece',
  unit_price: '4', currency: 'PHP', client_quantity: '9', reasons: [], catalog_code: 'M1',
  material_id: 5, units_per_purchase: '1', excluded: false }
const mapping = { kind:'client_bom', sheet:'CSV',header_row:1,columns:{code:'A',name:'B',unit:'C',unit_price:'D',currency:'E',quantity:'F'} }
const proposal = { file_sha256:'a'.repeat(64),preview_token:'b'.repeat(64),expected_version:0,
  ready:true,document:{mapping,rows:[row]},materials:[] }
beforeEach(() => {
  listProjectPrices.mockResolvedValue([])
  previewProjectPrices.mockResolvedValue(proposal)
  applyProjectPrices.mockResolvedValue(version)
  fetchProjectPrice.mockResolvedValue({ ...version, document:{rows:[row]} })
})
afterEach(() => { cleanup(); vi.resetAllMocks() })
function chooseFile() {
  const file = new File(['source'],'client.csv')
  fireEvent.change(screen.getByLabelText('Client file'),{target:{files:[file]}})
  return file
}
it('choosing a file automatically validates and applies prices without mapping tools or another confirmation', async () => {
  const onApplied = vi.fn()
  render(<ClientPricingPanel projectId={15} designer defaultImportOpen onApplied={onApplied} />)
  const file = chooseFile()
  await screen.findByText('Prices updated. Saved estimates are unchanged.')
  expect(previewProjectPrices).toHaveBeenCalledWith(15,file,null,expect.any(Object))
  expect(applyProjectPrices).toHaveBeenCalledWith(15,file,expect.objectContaining({
    automatic:true,confirmed:true,mapping,file_sha256:proposal.file_sha256,preview_token:proposal.preview_token,
    expected_version:0,choices:[{row_id:'CSV:2',material_id:5,units_per_purchase:'1',excluded:false}],
  }),expect.any(Object))
  expect(onApplied).toHaveBeenCalledWith(version)
  for (const label of ['Import type','Worksheet','Header row','Description column','Material for CSV:2'])
    expect(screen.queryByLabelText(label)).toBeNull()
  expect(screen.queryByRole('checkbox')).toBeNull()
  expect(screen.queryByRole('button',{name:/Read headers|Preview rows|Save & apply/})).toBeNull()
})
it('shows a concise source error without applying unknown or invalid materials', async () => {
  previewProjectPrices.mockRejectedValue(new ProjectPricingError(422,'Row 2: use an exact catalog Code or Description.'))
  render(<ClientPricingPanel projectId={15} designer defaultImportOpen />)
  chooseFile()
  expect((await screen.findByRole('alert')).textContent).toContain('Row 2')
  expect(applyProjectPrices).not.toHaveBeenCalled()
  expect(screen.getByLabelText('Client file').disabled).toBe(false)
})
it('never applies an unresolved preview or silently accepts partial matching', async () => {
  previewProjectPrices.mockResolvedValue({...proposal,ready:false})
  render(<ClientPricingPanel projectId={15} designer defaultImportOpen />)
  chooseFile()
  await screen.findByRole('alert')
  expect(applyProjectPrices).not.toHaveBeenCalled()
})
it('locks uncertain saves and retries the identical source and request without previewing twice', async () => {
  applyProjectPrices.mockRejectedValueOnce(new ProjectPricingError(503)).mockResolvedValueOnce(version)
  render(<ClientPricingPanel projectId={15} designer defaultImportOpen />)
  chooseFile()
  const retry = await screen.findByRole('button',{name:'Retry upload'})
  expect(screen.getByLabelText('Client file').disabled).toBe(true)
  const first=applyProjectPrices.mock.calls[0]
  fireEvent.click(retry)
  await screen.findByText('Prices updated. Saved estimates are unchanged.')
  expect(applyProjectPrices.mock.calls[1].slice(0,3)).toEqual(first.slice(0,3))
  expect(previewProjectPrices).toHaveBeenCalledTimes(1)
})
it('fences double file-selection events while an import is in flight', async () => {
  previewProjectPrices.mockReturnValue(new Promise(()=>{}))
  render(<ClientPricingPanel projectId={15} designer defaultImportOpen />)
  chooseFile();chooseFile()
  expect(previewProjectPrices).toHaveBeenCalledTimes(1)
  expect(screen.getByLabelText('Client file').disabled).toBe(true)
})
it('keeps client and calculated quantities separate in optional read-only history', async () => {
  listProjectPrices.mockResolvedValue([version])
  fetchProjectPrice.mockResolvedValue({...version,document:{rows:[row]},
    comparison:[{row_id:'CSV:2',client_quantity:'9',calculated_quantity:'2',difference:'-7',unit:'piece'}]})
  render(<ClientPricingPanel projectId={15} designer={false} estimateId={12} />)
  fireEvent.click(await screen.findByText('Previous uploads'))
  fireEvent.change(screen.getByLabelText('Saved client import'),{target:{value:'7'}})
  expect(await screen.findByText('-7')).toBeTruthy()
  expect(screen.getByText('9')).toBeTruthy()
  expect(screen.getByText('2 piece')).toBeTruthy()
  expect(screen.queryByLabelText('Client file')).toBeNull()
  expect(applyProjectPrices).not.toHaveBeenCalled()
})
it('drops comparison data when the estimate changes and fences stale responses', async () => {
  listProjectPrices.mockResolvedValue([version])
  const {rerender}=render(<ClientPricingPanel projectId={15} designer={false} estimateId={12}/>)
  fireEvent.click(await screen.findByText('Previous uploads'))
  fireEvent.change(screen.getByLabelText('Saved client import'),{target:{value:'7'}})
  await screen.findByText('Client lamp')
  fetchProjectPrice.mockReturnValue(new Promise(()=>{}))
  rerender(<ClientPricingPanel projectId={15} designer={false} estimateId={13}/>)
  expect(screen.queryByText('Client lamp')).toBeNull()
  await waitFor(()=>expect(fetchProjectPrice).toHaveBeenLastCalledWith(15,'7',expect.objectContaining({estimateId:13})))
})
