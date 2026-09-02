/* @vitest-environment jsdom */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ProtectedAppPage } from './ProtectedAppPage.jsx'

const viewerState = vi.hoisted(() => ({ shouldThrow: false }))

vi.mock('../projects/ProjectDashboardPage.jsx', () => ({ ProjectDashboardPage: () => <p>dashboard</p> }))
vi.mock('../projects/ProjectDetailPage.jsx', () => ({ ProjectDetailPage: () => <p>project</p> }))
vi.mock('../detection-review/DetectionReviewPage.jsx', () => ({
  DetectionReviewPage: ({ projectId, floorPlanId, processingJobId }) => (
    <p>review {projectId}/{floorPlanId}/{processingJobId}</p>
  ),
}))
vi.mock('../editor-2d/LayoutEditorPage.jsx', () => ({
  LayoutEditorPage: ({ projectId, projectFloorId }) => <p>layout {projectId}/{projectFloorId}</p>,
}))
vi.mock('../viewer-3d/Viewer3DPage.jsx', () => ({
  default: ({ projectId, projectFloorId }) => {
    if (viewerState.shouldThrow) throw new Error('renderer internals')
    return <p>viewer {projectId}/{projectFloorId}</p>
  },
}))

afterEach(() => {
  cleanup()
  viewerState.shouldThrow = false
  vi.restoreAllMocks()
})

describe('protected app detection route', () => {
  it('renders the detection review view with parsed identifiers', () => {
    const session = {
      status: 'authenticated', user: { display_name: 'Designer', role: 'DESIGNER' },
      signOut: vi.fn(), retry: vi.fn(), error: null, isSigningOut: false,
    }
    render(
      <ProtectedAppPage
        route="/app/projects/15/floor-plans/81/detections/103"
        session={session}
      />,
    )
    expect(screen.getByText('review 15/81/103')).toBeTruthy()
  })

  it('renders the current layout view with parsed identifiers', () => {
    const session = {
      status: 'authenticated', user: { display_name: 'Designer', role: 'DESIGNER' },
      signOut: vi.fn(), retry: vi.fn(), error: null, isSigningOut: false,
    }
    render(<ProtectedAppPage route="/app/projects/15/floors/2/layout" session={session} />)
    expect(screen.getByText('layout 15/2')).toBeTruthy()
  })

  it('lazy-loads the 3D viewer inside the authenticated shell', async () => {
    const session = {
      status: 'authenticated', user: { display_name: 'Designer', role: 'DESIGNER' },
      signOut: vi.fn(), retry: vi.fn(), error: null, isSigningOut: false,
    }
    render(<ProtectedAppPage route="/app/projects/15/floors/2/viewer-3d" session={session} />)
    expect(screen.getByRole('banner')).toBeTruthy()
    expect(screen.getByRole('status').textContent).toMatch(/Loading the 3D viewer/)
    expect(await screen.findByText('viewer 15/2')).toBeTruthy()
  })

  it('contains viewer failure and leaves the protected shell and other routes usable', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    viewerState.shouldThrow = true
    const session = {
      status: 'authenticated', user: { display_name: 'Designer', role: 'DESIGNER' },
      signOut: vi.fn(), retry: vi.fn(), error: null, isSigningOut: false,
    }
    const view = render(
      <ProtectedAppPage route="/app/projects/15/floors/2/viewer-3d" session={session} />,
    )
    expect(await screen.findByRole('heading', { name: '3D viewer unavailable' })).toBeTruthy()
    expect(screen.getByRole('banner')).toBeTruthy()
    expect(screen.getByRole('alert').textContent).not.toContain('renderer internals')

    view.unmount()
    viewerState.shouldThrow = false
    render(<ProtectedAppPage route="/app" session={session} />)
    expect(screen.getByText('dashboard')).toBeTruthy()
  })
})
