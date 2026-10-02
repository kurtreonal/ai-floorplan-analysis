/* @vitest-environment jsdom */

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  createProject,
  fetchProject,
  listProjects,
  ProjectApiError,
} from '../../api/projects.js'
import { CreateProjectForm } from './CreateProjectForm.jsx'
import { ProjectDashboardPage } from './ProjectDashboardPage.jsx'
import { ProjectDetailPage } from './ProjectDetailPage.jsx'


vi.mock('../../api/projects.js', async () => {
  const actual = await vi.importActual('../../api/projects.js')
  return {
    ...actual,
    createProject: vi.fn(),
    fetchProject: vi.fn(),
    listProjects: vi.fn(),
  }
})

const DESIGNER_SESSION = {
  user: {
    id: 10,
    display_name: 'D4 Designer',
    email: 'designer@example.test',
    role: 'DESIGNER',
  },
}

const ADMIN_SESSION = {
  user: {
    id: 1,
    display_name: 'D4 Admin',
    email: 'admin@example.test',
    role: 'ADMIN',
  },
}

const PROJECT = {
  id: 129,
  owner_id: 10,
  name: 'D4 Verification Project',
  status: 'needs_review',
  client_name: 'D4 Test Client',
  location: 'D4 Test Location',
  created_at: '2026-08-24T21:00:00',
  updated_at: '2026-08-24T22:00:00',
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('project dashboard', () => {
  it('shows an accessible loading state while D2 is pending', () => {
    listProjects.mockReturnValue(new Promise(() => {}))

    render(<ProjectDashboardPage session={DESIGNER_SESSION} />)

    expect(screen.getByRole('status').textContent).toContain('Loading projects')
  })

  it('shows the Designer empty state and creation interface', async () => {
    listProjects.mockResolvedValue([])

    render(<ProjectDashboardPage session={DESIGNER_SESSION} />)

    expect(await screen.findByText('No projects yet.')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Start a project workspace' })).toBeTruthy()
  })

  it('does not expose project creation to Admin users', async () => {
    listProjects.mockResolvedValue([])

    render(<ProjectDashboardPage session={ADMIN_SESSION} />)

    expect(await screen.findByText('No projects yet.')).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Start a project workspace' })).toBeNull()
    expect(screen.getByText('No projects are currently available for review.')).toBeTruthy()
  })

  it('renders D2 metadata and the backend-provided status', async () => {
    listProjects.mockResolvedValue([PROJECT])

    render(<ProjectDashboardPage session={DESIGNER_SESSION} />)

    expect(await screen.findByRole('heading', { name: PROJECT.name })).toBeTruthy()
    expect(screen.getByText(PROJECT.client_name)).toBeTruthy()
    expect(screen.getByText(PROJECT.location)).toBeTruthy()
    expect(within(screen.getByRole('heading', { name: PROJECT.name }).closest('article')).getByText('needs review')).toBeTruthy()
    expect(screen.getByRole('link', { name: `Open ${PROJECT.name}` }).getAttribute('href')).toBe(
      '#/app/projects/129',
    )
  })

  it('shows a safe list error and reloads through Retry', async () => {
    listProjects
      .mockRejectedValueOnce(new ProjectApiError('internal detail', 503))
      .mockResolvedValueOnce([PROJECT])

    render(<ProjectDashboardPage session={DESIGNER_SESSION} />)

    expect(await screen.findByText('Projects are temporarily unavailable.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('heading', { name: PROJECT.name })).toBeTruthy()
    expect(screen.queryByText('internal detail')).toBeNull()
  })

  it('filters real project metadata and status without changing the records', async () => {
    const second = { ...PROJECT, id: 130, name: 'Alpha workspace', client_name: 'Another client', status: 'draft', updated_at: '2026-08-25T22:00:00' }
    const records = [PROJECT, second]
    const original = JSON.stringify(records)
    listProjects.mockResolvedValue(records)
    render(<ProjectDashboardPage session={DESIGNER_SESSION} />)
    await screen.findByRole('heading', { name: PROJECT.name })
    fireEvent.change(screen.getByLabelText('Search projects'), { target: { value: 'Another client' } })
    expect(screen.queryByRole('link', { name: `Open ${PROJECT.name}` })).toBeNull()
    expect(screen.getByRole('link', { name: 'Open Alpha workspace' })).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Project status'), { target: { value: 'needs_review' } })
    expect(screen.getByText('No matching projects.')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Search projects'), { target: { value: '' } })
    expect(screen.getByRole('link', { name: `Open ${PROJECT.name}` })).toBeTruthy()
    expect(JSON.stringify(records)).toBe(original)
  })

  it('sorts only the displayed list by name or last update', async () => {
    const second = { ...PROJECT, id: 130, name: 'Alpha workspace', updated_at: '2026-08-23T22:00:00' }
    listProjects.mockResolvedValue([PROJECT, second])
    render(<ProjectDashboardPage session={DESIGNER_SESSION} />)
    await screen.findByRole('heading', { name: PROJECT.name })
    expect(screen.getAllByRole('link', { name: /^Open / }).map((link) => link.textContent)).toEqual(['Open project →', 'Open project →'])
    expect(screen.getAllByRole('link', { name: /^Open / })[0].getAttribute('href')).toBe('#/app/projects/129')
    fireEvent.change(screen.getByLabelText('Sort projects'), { target: { value: 'name' } })
    expect(screen.getAllByRole('link', { name: /^Open / })[0].getAttribute('href')).toBe('#/app/projects/130')
  })

  it('adds the backend-created project to the dashboard', async () => {
    listProjects.mockResolvedValue([])
    createProject.mockResolvedValue(PROJECT)

    render(<ProjectDashboardPage session={DESIGNER_SESSION} />)
    await screen.findByText('No projects yet.')
    fireEvent.change(screen.getByLabelText('Project name'), {
      target: { value: `  ${PROJECT.name}  ` },
    })
    fireEvent.change(screen.getByLabelText(/Client name/), {
      target: { value: `  ${PROJECT.client_name}  ` },
    })
    fireEvent.change(screen.getByLabelText(/Location/), {
      target: { value: `  ${PROJECT.location}  ` },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create project' }))

    expect(await screen.findByRole('heading', { name: PROJECT.name })).toBeTruthy()
    expect(createProject).toHaveBeenCalledWith(
      {
        name: PROJECT.name,
        client_name: PROJECT.client_name,
        location: PROJECT.location,
      },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(within(screen.getByRole('heading', { name: PROJECT.name }).closest('article')).getByText('needs review')).toBeTruthy()
  })
})

describe('project creation form', () => {
  it('shows submission state and prevents duplicate submission', async () => {
    let resolveCreation
    createProject.mockReturnValue(new Promise((resolve) => {
      resolveCreation = resolve
    }))
    const onCreated = vi.fn()

    render(<CreateProjectForm onCreated={onCreated} />)
    fireEvent.change(screen.getByLabelText('Project name'), {
      target: { value: PROJECT.name },
    })
    const submit = screen.getByRole('button', { name: 'Create project' })
    fireEvent.click(submit)

    const submitting = screen.getByRole('button', { name: 'Creating project…' })
    expect(submitting.disabled).toBe(true)
    fireEvent.click(submitting)
    expect(createProject).toHaveBeenCalledTimes(1)

    await act(async () => resolveCreation(PROJECT))
    expect(onCreated).toHaveBeenCalledWith(PROJECT)
  })

  it('preserves useful input and shows a sanitized creation error', async () => {
    createProject.mockRejectedValue(new ProjectApiError('database internals', 503))

    render(<CreateProjectForm onCreated={vi.fn()} />)
    const nameInput = screen.getByLabelText('Project name')
    fireEvent.change(nameInput, { target: { value: PROJECT.name } })
    fireEvent.click(screen.getByRole('button', { name: 'Create project' }))

    expect(await screen.findByText('Project creation is temporarily unavailable.')).toBeTruthy()
    expect(nameInput.value).toBe(PROJECT.name)
    expect(screen.queryByText('database internals')).toBeNull()
  })
})

describe('project detail', () => {
  it('loads and renders D3 metadata with dashboard navigation', async () => {
    fetchProject.mockResolvedValue(PROJECT)

    render(<ProjectDetailPage projectId={PROJECT.id} />)

    expect(screen.getByRole('status').textContent).toContain('Loading project details')
    expect(await screen.findByRole('heading', { name: PROJECT.name })).toBeTruthy()
    expect(fetchProject).toHaveBeenCalledWith(
      PROJECT.id,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(screen.getByText('needs review')).toBeTruthy()
    expect(screen.getByText(PROJECT.client_name)).toBeTruthy()
    expect(screen.getByText(PROJECT.location)).toBeTruthy()
    expect(screen.getByRole('link', { name: /Back to dashboard/ }).getAttribute('href')).toBe('#/app')
    expect(screen.getByText(/upload original floor-plan files/i)).toBeTruthy()
    expect(screen.queryByText(/AI results/i)).toBeNull()
  })

  it('renders a clean D3 not-found state', async () => {
    fetchProject.mockRejectedValue(new ProjectApiError('private details', 404))

    render(<ProjectDetailPage projectId={999999} />)

    expect(await screen.findByText('The requested project was not found.')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Back to dashboard' }).getAttribute('href')).toBe('#/app')
    expect(screen.queryByText('private details')).toBeNull()
  })

  it('handles an invalid project route without making a request', () => {
    render(<ProjectDetailPage projectId={null} />)

    expect(screen.getByText('The project address is invalid.')).toBeTruthy()
    expect(fetchProject).not.toHaveBeenCalled()
  })
})
