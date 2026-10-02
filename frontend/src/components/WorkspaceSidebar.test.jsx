/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { WorkspaceSidebar } from './WorkspaceSidebar.jsx'

afterEach(cleanup)
const session = { user: { display_name: 'VED Designer', role: 'DESIGNER' }, signOut: vi.fn(), isSigningOut: false }

it('uses real project/floor routes and marks the current view', () => {
  render(<WorkspaceSidebar projectRoute={{ view: 'layout', projectId: 15, projectFloorId: 2 }} session={session} />)
  expect(screen.getByRole('link', { name: '2D editor' }).getAttribute('aria-current')).toBe('page')
  expect(screen.getByRole('link', { name: '3D viewer' }).getAttribute('href')).toBe('#/app/projects/15/floors/2/viewer-3d')
  expect(screen.getByRole('link', { name: 'Cost estimation' }).getAttribute('href')).toBe('#/app/projects/15/estimates')
  expect(screen.queryByRole('link', { name: 'Legend administration' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))
  expect(session.signOut).toHaveBeenCalledTimes(1)
})

it('does not invent a floor and exposes administration only for Admin', () => {
  render(<WorkspaceSidebar projectRoute={{ view: 'project', projectId: 15 }} session={{ ...session, user: { role: 'ADMIN' } }} />)
  expect(screen.queryByRole('link', { name: '2D editor' })).toBeNull()
  expect(screen.getAllByText('Choose a floor in the project')).toHaveLength(2)
  expect(screen.getByRole('link', { name: 'Legend administration' })).toBeTruthy()
})

it('does not bypass the editor save guard through a sidebar link', () => {
  const projectRoute = { view: 'layout', projectId: 15, projectFloorId: 2 }
  const { rerender } = render(<WorkspaceSidebar projectRoute={projectRoute} session={session} navigationBlocked />)
  expect(fireEvent.click(screen.getByRole('link', { name: '3D viewer' }))).toBe(false)
  expect(screen.getByRole('alert').textContent).toContain('Save or cancel')
  rerender(<WorkspaceSidebar projectRoute={projectRoute} session={session} navigationBlocked={false} />)
  expect(screen.queryByRole('alert')).toBeNull()
  expect(fireEvent.click(screen.getByRole('link', { name: '3D viewer' }))).toBe(true)
})

it('opens an accessible modal navigation sheet and closes on navigation', async () => {
  render(<WorkspaceSidebar projectRoute={{ view: 'dashboard' }} session={session} />)
  const trigger = screen.getByRole('button', { name: 'Open workspace navigation' })
  fireEvent.click(trigger)
  const dialog = await screen.findByRole('dialog', { name: 'Workspace navigation' })
  expect(dialog.getAttribute('aria-describedby')).toBeTruthy()
  await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true))
  fireEvent.click(within(dialog).getByRole('link', { name: 'Projects' }))
  expect(screen.queryByRole('dialog')).toBeNull()
  fireEvent.click(trigger)
  fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Close navigation' }))
  expect(screen.queryByRole('dialog')).toBeNull()
  await waitFor(() => expect(document.activeElement).toBe(trigger))
})
