/* @vitest-environment jsdom */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchAnalysisSettings, saveFloorElevation, savePageScale, AnalysisSettingsError } from '../../api/analysisSettings.js'
import { AnalysisSettingsPanel } from './AnalysisSettingsPanel.jsx'

vi.mock('../../api/analysisSettings.js', async () => ({
  ...await vi.importActual('../../api/analysisSettings.js'),
  fetchAnalysisSettings: vi.fn(), saveFloorElevation: vi.fn(), savePageScale: vi.fn(),
}))

const metadata = { revision_id: null, state: 'unresolved', evidence_notes: null, reviewed_by_user_id: null, created_at: null }
const fixture = {
  project_floor_id: 2,
  elevation: { ...metadata, unit: 'meter', elevation_meters: null },
  pages: [{ floor_plan_id: 3, floor_plan_page_id: 4, page_number: 1,
    scale: { ...metadata, unit: 'pixels_per_meter', pixels_per_meter: null, reference_width_pixels: null, reference_height_pixels: null } }],
}

beforeEach(() => { vi.clearAllMocks(); fetchAnalysisSettings.mockResolvedValue(structuredClone(fixture)) })
afterEach(cleanup)

async function open(canEdit = true) {
  const result = render(<AnalysisSettingsPanel projectId={1} floorId={2} canEdit={canEdit} />)
  fireEvent.click(screen.getByRole('button', { name: 'Review scale and elevation' }))
  await screen.findByRole('heading', { name: 'Floor elevation' })
  return result
}

describe('reviewed metric settings', () => {
  it('loads on demand and leaves unknown metric inputs blank', async () => {
    render(<AnalysisSettingsPanel projectId={1} floorId={2} canEdit />)
    expect(fetchAnalysisSettings).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Review scale and elevation' }))
    const elevation = await screen.findByLabelText('Floor elevation (meters from project datum)')
    expect(elevation.value).toBe('')
    expect(screen.getByLabelText('Scale (pixels per meter)').value).toBe('')
    expect(screen.getAllByText('Unresolved — requires Designer review')).toHaveLength(2)
  })

  it('saves explicit zero elevation and evidence without client reviewer identity', async () => {
    saveFloorElevation.mockResolvedValue({ ...fixture.elevation, revision_id: 8, state: 'approved', elevation_meters: 0, evidence_notes: 'Survey datum', reviewed_by_user_id: 9, created_at: '2026-09-05T00:00:00' })
    await open()
    const form = screen.getByLabelText('Floor elevation (meters from project datum)').closest('form')
    fireEvent.change(within(form).getByRole('spinbutton'), { target: { value: '0' } })
    fireEvent.change(within(form).getByLabelText('Evidence notes'), { target: { value: 'Survey datum' } })
    fireEvent.submit(form)
    await screen.findByText('Designer-approved')
    expect(saveFloorElevation).toHaveBeenCalledWith(1, 2, { elevation_meters: 0, evidence_notes: 'Survey datum' }, expect.objectContaining({ signal: expect.any(AbortSignal) }))
  })

  it('saves page scale with both reference dimensions and permits unresolved state', async () => {
    savePageScale.mockResolvedValue({ ...fixture.pages[0].scale, revision_id: 10 })
    await open()
    const form = screen.getByLabelText('Scale (pixels per meter)').closest('form')
    fireEvent.change(within(form).getByLabelText('Scale (pixels per meter)'), { target: { value: '100' } })
    fireEvent.change(within(form).getByLabelText('Reference image width (pixels)'), { target: { value: '1000' } })
    fireEvent.change(within(form).getByLabelText('Reference image height (pixels)'), { target: { value: '500' } })
    fireEvent.change(within(form).getByLabelText('Evidence notes'), { target: { value: 'Measured 500 pixels over 5 meters' } })
    fireEvent.submit(form)
    await waitFor(() => expect(savePageScale).toHaveBeenCalledWith(1, 2, 4, { pixels_per_meter: 100, reference_width_pixels: 1000, reference_height_pixels: 500, evidence_notes: 'Measured 500 pixels over 5 meters' }, expect.any(Object)))
  })

  it('renders Admin inspection without a save action', async () => {
    await open(false)
    expect(screen.queryByRole('button', { name: 'Save reviewed settings' })).toBeNull()
    expect(screen.getByLabelText('Scale (pixels per meter)').closest('fieldset').disabled).toBe(true)
    expect(savePageScale).not.toHaveBeenCalled()
  })

  it('shows safe save failures and preserves the editable measurement', async () => {
    saveFloorElevation.mockRejectedValue(new AnalysisSettingsError(503))
    await open()
    const input = screen.getByLabelText('Floor elevation (meters from project datum)')
    fireEvent.change(input, { target: { value: '3' } })
    fireEvent.change(within(input.closest('form')).getByLabelText('Evidence notes'), { target: { value: 'Survey' } })
    fireEvent.submit(input.closest('form'))
    expect((await screen.findByRole('alert')).textContent).toContain('unavailable')
    expect(input.value).toBe('3')
  })

  it('aborts and ignores a late response after leaving the floor', async () => {
    let resolve
    fetchAnalysisSettings.mockReturnValue(new Promise((done) => { resolve = done }))
    const view = render(<AnalysisSettingsPanel projectId={1} floorId={2} canEdit />)
    fireEvent.click(screen.getByRole('button', { name: 'Review scale and elevation' }))
    const signal = fetchAnalysisSettings.mock.calls[0][2].signal
    view.unmount()
    expect(signal.aborted).toBe(true)
    await act(async () => resolve(fixture))
    expect(saveFloorElevation).not.toHaveBeenCalled()
  })
})
