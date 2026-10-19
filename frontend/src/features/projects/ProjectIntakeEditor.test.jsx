/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ProjectApiError, updateProject } from '../../api/projects.js'
import { ProjectIntakeEditor } from './ProjectIntakeEditor.jsx'
import { CreateProjectForm } from './CreateProjectForm.jsx'
import { createProject } from '../../api/projects.js'
vi.mock('../../api/projects.js', async () => ({ ...await vi.importActual('../../api/projects.js'), updateProject: vi.fn(), createProject: vi.fn() }))
const project = { id: 22, name: 'Synthetic intake', client_name: null, location: null, contact_number: '000123',
  service_type: null, service_type_other: null, preferred_start_date: null, blueprint_availability: null, details_revision: 'a'.repeat(64) }
afterEach(() => { cleanup(); vi.resetAllMocks() })

it('creates without an upload and hands Available now to the existing project flow', async () => {
  createProject.mockResolvedValue({ ...project, blueprint_availability: 'available_now' })
  const created = vi.fn()
  render(<CreateProjectForm onCreated={created} />)
  fireEvent.change(screen.getByLabelText('Project name'), { target: { value: project.name } })
  fireEvent.change(screen.getByLabelText(/Contact number/), { target: { value: '+63 000123' } })
  fireEvent.change(screen.getByLabelText('Blueprint availability'), { target: { value: 'available_now' } })
  fireEvent.change(screen.getByLabelText('Preferred start date'), { target: { value: '2027-01-05' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create project' }))
  expect((await screen.findByRole('link', { name: 'Continue to floors & upload' })).getAttribute('href')).toBe('#/app/projects/22')
  expect(createProject).toHaveBeenCalledWith(expect.objectContaining({ contact_number: '+63 000123', preferred_start_date: '2027-01-05', blueprint_availability: 'available_now' }), expect.any(Object))
  expect(screen.queryByLabelText(/file/i)).toBeNull()
})

it('edits nullable metadata, date and exact phone string with an expected revision', async () => {
  const saved = { ...project, contact_number: '+63 (02) 0012', service_type: 'other', service_type_other: 'Inspection', preferred_start_date: '2027-01-05', details_revision: 'b'.repeat(64) }
  updateProject.mockResolvedValue(saved)
  const onSaved = vi.fn()
  render(<ProjectIntakeEditor project={project} onSaved={onSaved} />)
  fireEvent.click(screen.getByText('Edit project details'))
  expect(screen.getByLabelText(/Contact number/).value).toBe('000123')
  fireEvent.change(screen.getByLabelText(/Contact number/), { target: { value: saved.contact_number } })
  fireEvent.change(screen.getByLabelText('Project / service type'), { target: { value: 'other' } })
  fireEvent.change(screen.getByLabelText('Other project / service type'), { target: { value: 'Inspection' } })
  fireEvent.change(screen.getByLabelText('Preferred start date'), { target: { value: '2027-01-05' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save project details' }))
  await screen.findByText('Project details saved.')
  expect(updateProject).toHaveBeenCalledWith(22, expect.objectContaining({ contact_number: saved.contact_number, service_type: 'other', service_type_other: 'Inspection', preferred_start_date: '2027-01-05', blueprint_availability: null, expected_details_revision: project.details_revision }), expect.any(Object))
  expect(onSaved).toHaveBeenCalledWith(saved)
})

it('keeps inputs on conflict and only reloads when explicitly discarded', async () => {
  updateProject.mockRejectedValue(new ProjectApiError('private internals', 409))
  const onReload = vi.fn()
  render(<ProjectIntakeEditor project={project} onReload={onReload} />)
  fireEvent.click(screen.getByText('Edit project details'))
  fireEvent.change(screen.getByLabelText('Project name'), { target: { value: 'Unsaved edit' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save project details' }))
  await screen.findByText(/Project details changed elsewhere/)
  expect(screen.getByLabelText('Project name').value).toBe('Unsaved edit')
  expect(screen.queryByText('private internals')).toBeNull()
  expect(onReload).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Discard edits & reload' }))
  expect(onReload).toHaveBeenCalledOnce()
})

it('locks an uncertain edit and retries the identical payload', async () => {
  updateProject.mockRejectedValueOnce(new ProjectApiError('unknown', 503)).mockResolvedValue(project)
  render(<ProjectIntakeEditor project={project} onSaved={vi.fn()} />)
  fireEvent.click(screen.getByText('Edit project details'))
  fireEvent.click(screen.getByRole('button', { name: 'Save project details' }))
  await screen.findByText(/Save result uncertain/)
  expect(screen.getByLabelText('Project name').disabled).toBe(true)
  const first = updateProject.mock.calls[0][1]
  fireEvent.click(screen.getByRole('button', { name: 'Retry same details' }))
  await screen.findByText('Project details saved.')
  expect(updateProject.mock.calls[1][1]).toEqual(first)
})
