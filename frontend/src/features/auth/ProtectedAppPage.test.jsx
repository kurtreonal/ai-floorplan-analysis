/* @vitest-environment jsdom */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ProtectedAppPage } from './ProtectedAppPage.jsx'

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

afterEach(cleanup)

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
})
