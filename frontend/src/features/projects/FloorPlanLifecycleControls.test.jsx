/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { FloorPlanLifecycleControls, FloorPlanTrash } from './FloorPlanLifecycleControls.jsx'
import { floorPlanLifecycle } from '../../api/floorPlanLifecycle.js'
import { FloorPlanApiError } from '../../api/floorPlans.js'

vi.mock('../../api/floorPlanLifecycle.js', () => ({ floorPlanLifecycle: vi.fn() }))
const info = { id: 9, project_floor_id: 4, original_filename: 'exact-target.png',
  revision: 0, removed: false, active_jobs: 2, saved_layouts: 3, saved_reviews: 4 }
beforeEach(() => {
  vi.clearAllMocks()
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
})
afterEach(cleanup)

describe('recoverable floor-plan management', () => {
  it('loads the exact target and consequences, then requires explicit confirmation', async () => {
    floorPlanLifecycle.mockResolvedValueOnce(info).mockResolvedValueOnce({ ...info, removed: true, revision: 1 })
    const changed = vi.fn()
    render(<FloorPlanLifecycleControls projectId={2} planId={9} onChanged={changed} />)
    fireEvent.click(screen.getByText('Move to trash'))
    await screen.findByText('exact-target.png')
    expect(screen.getByText('Plan #9 · Floor #4')).toBeTruthy()
    expect(screen.getByText(/2 unfinished analysis/)).toBeTruthy()
    expect(screen.getByText(/3 saved layout/)).toBeTruthy()
    expect(floorPlanLifecycle).toHaveBeenCalledTimes(1)
    fireEvent.click(await screen.findByRole('button', { name: 'Move floor plan to trash' }))
    await waitFor(() => expect(changed).toHaveBeenCalledWith(9))
    expect(floorPlanLifecycle.mock.calls[1][2]).toMatchObject({ method: 'DELETE', body: { expected_revision: 0 } })
  })
  it('cancels without mutating and restores focus', async () => {
    floorPlanLifecycle.mockResolvedValue(info)
    render(<FloorPlanLifecycleControls projectId={2} planId={9} onChanged={vi.fn()} />)
    fireEvent.click(screen.getByText('Move to trash'))
    await screen.findByText('exact-target.png')
    fireEvent.click(screen.getByText('Cancel'))
    expect(floorPlanLifecycle).toHaveBeenCalledTimes(1)
    expect(document.activeElement.textContent).toBe('Move to trash')
  })
  it('retries an uncertain mutation with the exact same request identity', async () => {
    floorPlanLifecycle.mockResolvedValueOnce(info).mockRejectedValueOnce(new FloorPlanApiError('Interrupted.', 503))
      .mockResolvedValueOnce({ ...info, removed: true, revision: 1 })
    const changed = vi.fn()
    render(<FloorPlanLifecycleControls projectId={2} planId={9} onChanged={changed} />)
    fireEvent.click(screen.getByText('Move to trash'))
    await screen.findByText('exact-target.png')
    fireEvent.click(await screen.findByRole('button', { name: 'Move floor plan to trash' }))
    await screen.findByText('Interrupted.')
    fireEvent.click(screen.getByText('Retry same request'))
    await waitFor(() => expect(changed).toHaveBeenCalledTimes(1))
    expect(floorPlanLifecycle.mock.calls[2][2].body).toEqual(floorPlanLifecycle.mock.calls[1][2].body)
  })
  it('keeps trash closed by default and Admin restore controls unavailable', async () => {
    floorPlanLifecycle.mockResolvedValue([{ ...info, removed: true, revision: 1 }])
    render(<FloorPlanTrash projectId={2} refreshKey={0} onChanged={vi.fn()} canEdit={false} />)
    expect(floorPlanLifecycle).not.toHaveBeenCalled()
    const details = screen.getByText('Trash').parentElement
    details.open = true
    fireEvent(details, new Event('toggle', { bubbles: true }))
    await screen.findByText('exact-target.png · Floor #4')
    expect(screen.queryByRole('button', { name: 'Restore' })).toBeNull()
  })
  it('restores only after confirmation and explains that jobs do not restart', async () => {
    floorPlanLifecycle.mockResolvedValueOnce({ ...info, removed: true, revision: 1 }).mockResolvedValueOnce(info)
    const changed = vi.fn()
    render(<FloorPlanLifecycleControls projectId={2} planId={9} restore onChanged={changed} />)
    fireEvent.click(screen.getByText('Restore'))
    await screen.findByText(/Cancelled analysis will not restart/)
    fireEvent.click(await screen.findByRole('button', { name: 'Restore floor plan' }))
    await waitFor(() => expect(changed).toHaveBeenCalledTimes(1))
    expect(floorPlanLifecycle.mock.calls[1]).toMatchObject([2, 'floor-plans/9/restore', { method: 'POST' }])
  })
})
