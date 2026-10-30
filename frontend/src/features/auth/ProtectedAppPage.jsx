import { lazy, Suspense, useEffect, useState } from 'react'

import { WorkspaceSidebar } from '../../components/WorkspaceSidebar.jsx'
import { getProtectedRouteRedirect } from '../../routes/authRoutes.js'
import { parseProjectRoute } from '../../routes/projectRoutes.js'
import { ProjectDashboardPage } from '../projects/ProjectDashboardPage.jsx'
import { ProjectDetailPage } from '../projects/ProjectDetailPage.jsx'
import { DetectionReviewPage } from '../detection-review/DetectionReviewPage.jsx'
import { DemoInterpretationPage } from '../detection-review/DemoInterpretationPage.jsx'
import { LayoutEditorPage } from '../editor-2d/LayoutEditorPage.jsx'
import { EstimatePage } from '../estimation/EstimatePage.jsx'
import { Viewer3DErrorBoundary } from '../viewer-3d/Viewer3DErrorBoundary.jsx'
import '../projects/projects.css'
import '../../components/workspace.css'
import { UserPreferencesProvider } from '../settings/UserPreferences.jsx'
import { UserSettingsPage } from '../settings/UserSettingsPage.jsx'
import { AuthRecoveryScreen } from './AuthRecoveryScreen.jsx'
import { ClientPortal } from '../projects/ClientPortal.jsx'
import '../projects/clientWorkflow.css'
import { MutationNotifications } from '../../components/MutationNotifications.jsx'
import { NotificationCenter } from '../../components/NotificationCenter.jsx'

const Viewer3DPage = lazy(() => import('../viewer-3d/Viewer3DPage.jsx'))

export function ProtectedAppPage({ route, session }) {
  const [navigationBlocked, setNavigationBlocked] = useState(false)
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
    return <AuthRecoveryScreen onRetry={session.retry} unavailable />
  }

  const projectRoute = parseProjectRoute(route)

  return (
    <UserPreferencesProvider key={session.user.id ?? session.user.email ?? 'session'} userId={session.user.id ?? session.user.email ?? 'session'} loadSharedDefaults={session.user.role !== 'CLIENT'}>
    <MutationNotifications/>
    <div className={`project-app studio-shell${projectRoute.view === 'demo-interpretation' ? ' studio-canvas-first' : ''}`}>
      <WorkspaceSidebar projectRoute={projectRoute} session={session} navigationBlocked={navigationBlocked} />
      <div className="studio-content">
      <header className="studio-topbar"><div className="studio-topbar-start">{projectRoute.view!=='demo-interpretation' && session.user.role==='DESIGNER' && <NotificationCenter/>}<span className="mono">VED / {projectRoute.projectId ? `PROJECT ${projectRoute.projectId}` : 'PROJECTS'}</span></div><span>Planning & estimation · review before use</span></header>

      {session.error && (
        <div className="auth-message auth-message-error project-shell-error" role="alert">
          {session.error}
        </div>
      )}

      <main className="project-app-main">
        {projectRoute.view === 'settings' && <UserSettingsPage isAdmin={session.user.role==='ADMIN'}/>}
        {session.user.role === 'CLIENT' && projectRoute.view !== 'settings' ? <ClientPortal/> : <>
        {projectRoute.view === 'dashboard' && <ProjectDashboardPage key={`${projectRoute.section || 'dashboard'}:${projectRoute.clientFilter || ''}`} session={session} initialSection={projectRoute.section} clientFilter={projectRoute.clientFilter} />}
        {projectRoute.view === 'project' && (
          <ProjectDetailPage projectId={projectRoute.projectId} session={session} />
        )}
        {projectRoute.view === 'estimates' && <EstimatePage key={projectRoute.projectId} projectId={projectRoute.projectId} session={session} />}
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
            measurementAction={projectRoute.measurementAction}
            measurementTarget={projectRoute.measurementTarget}
            measurementTargets={projectRoute.measurementTargets}
            session={session}
          />
        )}
        {projectRoute.view === 'layout' && (
          <LayoutEditorPage
            key={`${projectRoute.projectId}-${projectRoute.projectFloorId}`}
            projectId={projectRoute.projectId}
            projectFloorId={projectRoute.projectFloorId}
            session={session}
            onDirtyChange={setNavigationBlocked}
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
        </>}
      </main>
      </div>
    </div>
    </UserPreferencesProvider>
  )
}
