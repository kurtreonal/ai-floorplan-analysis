import { lazy, Suspense, useEffect } from 'react'

import vedLogo from '../../assets/ved-logo.png'
import { getProtectedRouteRedirect } from '../../routes/authRoutes.js'
import { parseProjectRoute } from '../../routes/projectRoutes.js'
import { ProjectDashboardPage } from '../projects/ProjectDashboardPage.jsx'
import { ProjectDetailPage } from '../projects/ProjectDetailPage.jsx'
import { DetectionReviewPage } from '../detection-review/DetectionReviewPage.jsx'
import { DemoInterpretationPage } from '../detection-review/DemoInterpretationPage.jsx'
import { LayoutEditorPage } from '../editor-2d/LayoutEditorPage.jsx'
import { Viewer3DErrorBoundary } from '../viewer-3d/Viewer3DErrorBoundary.jsx'
import '../projects/projects.css'

const Viewer3DPage = lazy(() => import('../viewer-3d/Viewer3DPage.jsx'))

export function ProtectedAppPage({ route, session }) {
  useEffect(() => {
    const redirect = getProtectedRouteRedirect(session.status)
    if (redirect) {
      window.location.replace(redirect)
    }
  }, [session.status])

  if (session.status === 'loading' || session.status === 'unauthenticated') {
    return (
      <main className="auth-shell">
        <div className="auth-message auth-route-status" role="status">
          <span className="auth-spinner" aria-hidden="true" />
          Verifying application access…
        </div>
      </main>
    )
  }

  if (session.status === 'error') {
    return (
      <main className="auth-shell">
        <section className="auth-card" aria-labelledby="access-error-title">
          <div className="auth-card-accent mono">APPLICATION ACCESS</div>
          <h1 id="access-error-title">We couldn’t verify your session.</h1>
          <p className="auth-intro">The authentication service may be temporarily unavailable.</p>
          <button className="btn btn-accent auth-primary" type="button" onClick={session.retry}>
            Try again
          </button>
          <a className="auth-home-link" href="#/">← Return to home</a>
        </section>
      </main>
    )
  }

  const projectRoute = parseProjectRoute(route)
  const displayName = session.user.display_name || session.user.email || 'VED user'

  return (
    <div className="project-app">
      <header className="project-app-header">
        <a className="project-app-brand" href="#/app" aria-label="VED project dashboard">
          <img src={vedLogo} alt="VED Electrical Services" />
        </a>
        <div className="project-user-controls">
          <div className="project-user-summary">
            <strong>{displayName}</strong>
            <span className="mono">{session.user.role}</span>
          </div>
          <button
            className="btn btn-ghost project-sign-out"
            type="button"
            disabled={session.isSigningOut}
            onClick={session.signOut}
          >
            {session.isSigningOut ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      </header>

      {session.error && (
        <div className="auth-message auth-message-error project-shell-error" role="alert">
          {session.error}
        </div>
      )}

      <main className="project-app-main">
        {projectRoute.view === 'dashboard' && <ProjectDashboardPage session={session} />}
        {projectRoute.view === 'project' && (
          <ProjectDetailPage projectId={projectRoute.projectId} session={session} />
        )}
        {projectRoute.view === 'detection-review' && (
          <DetectionReviewPage
            key={`${projectRoute.projectId}-${projectRoute.floorPlanId}-${projectRoute.processingJobId}`}
            projectId={projectRoute.projectId}
            floorPlanId={projectRoute.floorPlanId}
            processingJobId={projectRoute.processingJobId}
          />
        )}
        {projectRoute.view === 'demo-interpretation' && (
          <DemoInterpretationPage
            key={`${projectRoute.projectId}-${projectRoute.projectFloorId}-${projectRoute.floorPlanId}-${projectRoute.processingJobId}`}
            projectId={projectRoute.projectId}
            projectFloorId={projectRoute.projectFloorId}
            floorPlanId={projectRoute.floorPlanId}
            processingJobId={projectRoute.processingJobId}
          />
        )}
        {projectRoute.view === 'layout' && (
          <LayoutEditorPage
            key={`${projectRoute.projectId}-${projectRoute.projectFloorId}`}
            projectId={projectRoute.projectId}
            projectFloorId={projectRoute.projectFloorId}
            session={session}
          />
        )}
        {projectRoute.view === 'viewer-3d' && (
          <Viewer3DErrorBoundary
            key={`${projectRoute.projectId}-${projectRoute.projectFloorId}`}
            projectId={projectRoute.projectId}
            title="3D viewer unavailable"
          >
            <Suspense fallback={<div className="viewer-3d-route-state" role="status">Loading the 3D viewer…</div>}>
              <Viewer3DPage
                projectId={projectRoute.projectId}
                projectFloorId={projectRoute.projectFloorId}
              />
            </Suspense>
          </Viewer3DErrorBoundary>
        )}
        {projectRoute.view === 'invalid' && (
          <ProjectDetailPage projectId={null} session={session} />
        )}
      </main>
    </div>
  )
}
