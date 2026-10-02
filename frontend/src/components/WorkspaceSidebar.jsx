import { useState } from 'react'
import { Box, Calculator, FolderOpen, Layers3, LayoutDashboard, LogOut, Menu, ScanLine, ShieldCheck } from 'lucide-react'
import vedLogo from '../assets/ved-logo.png'
import { getEstimateHref, getLayoutHref, getProjectHref, getViewer3dHref } from '../routes/projectRoutes.js'
import { Button } from './ui/button.jsx'
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from './ui/sheet.jsx'

function Navigation({ projectRoute, session, onNavigate }) {
  const { projectId, projectFloorId, view } = projectRoute
  const links = [
    { label: 'Projects', icon: LayoutDashboard, href: '#/app', active: view === 'dashboard' },
    ...(projectId ? [
      { label: 'Project workspace', icon: FolderOpen, href: getProjectHref(projectId), active: view === 'project' },
      { label: '2D editor', icon: Layers3, href: projectFloorId ? getLayoutHref(projectId, projectFloorId) : null, active: view === 'layout' },
      { label: '3D viewer', icon: Box, href: projectFloorId ? getViewer3dHref(projectId, projectFloorId) : null, active: view === 'viewer-3d' },
      { label: 'Cost estimation', icon: Calculator, href: getEstimateHref(projectId), active: view === 'estimates' },
    ] : []),
  ]
  return <>
    <a className="studio-brand" href="#/app" onClick={onNavigate} aria-label="VED project dashboard">
      <img src={vedLogo} alt="VED Electrical Services" /><span>Electrical workspace<small className="mono">PLAN · REVIEW · ESTIMATE</small></span>
    </a>
    <nav className="studio-navigation" aria-label="Workspace navigation">
      <p className="mono">WORKSPACE</p>
      {links.map(({ label, icon: Icon, href, active }) => href
        ? <a key={label} href={href} onClick={onNavigate} aria-current={active ? 'page' : undefined}><Icon aria-hidden="true" /><span>{label}</span></a>
        : <span key={label} className="studio-nav-unavailable"><Icon aria-hidden="true" /><span>{label}<small>Choose a floor in the project</small></span></span>)}
      {['detection-review', 'demo-interpretation'].includes(view) && <span className="studio-nav-context"><ScanLine aria-hidden="true" />AI proposal review</span>}
      {session.user.role === 'ADMIN' && <><p className="mono">ADMINISTRATION</p><a href="#/app" onClick={onNavigate}><ShieldCheck aria-hidden="true" />Legend administration</a></>}
    </nav>
    <div className="studio-boundary"><ShieldCheck aria-hidden="true" /><div><strong>Local planning workspace</strong><p>Originals preserved. AI proposals require review.</p></div></div>
    <div className="studio-profile"><span className="studio-avatar" aria-hidden="true">{(session.user.display_name || 'VED').slice(0, 2).toUpperCase()}</span><div><strong>{session.user.display_name || session.user.email || 'VED user'}</strong><small className="mono">{session.user.role}</small></div></div>
    <Button variant="outline" className="studio-sign-out" disabled={session.isSigningOut} onClick={session.signOut}><LogOut aria-hidden="true" />{session.isSigningOut ? 'Signing out…' : 'Sign out'}</Button>
  </>
}

export function WorkspaceSidebar({ projectRoute, session, navigationBlocked = false }) {
  const [open, setOpen] = useState(false)
  const [showBlockedNotice, setShowBlockedNotice] = useState(false)
  function handleNavigate(event) {
    if (navigationBlocked && event.currentTarget.getAttribute('href') !== window.location.hash) {
      event.preventDefault()
      setShowBlockedNotice(true)
      return
    }
    setShowBlockedNotice(false)
    setOpen(false)
  }
  const notice = showBlockedNotice && navigationBlocked && <p className="studio-navigation-warning" role="alert">Save or cancel your position changes before leaving this editor.</p>
  return <>
    <aside className="studio-sidebar"><Navigation projectRoute={projectRoute} session={session} onNavigate={handleNavigate} />{notice}</aside>
    <div className="studio-mobile-navigation"><Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild><Button variant="outline" size="icon" aria-label="Open workspace navigation"><Menu aria-hidden="true" /></Button></SheetTrigger>
      <SheetContent><SheetTitle className="sr-only">Workspace navigation</SheetTitle><SheetDescription className="sr-only">Navigate your VED planning workspace.</SheetDescription><Navigation projectRoute={projectRoute} session={session} onNavigate={handleNavigate} />{notice}</SheetContent>
    </Sheet></div>
  </>
}
