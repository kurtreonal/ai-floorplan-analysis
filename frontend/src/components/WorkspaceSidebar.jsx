import { useState } from 'react'
import { LayoutDashboard, LogOut, Menu, Settings, ShieldCheck, Users } from 'lucide-react'
import vedLogo from '../assets/ved-logo.png'
import { getProjectHref } from '../routes/projectRoutes.js'
import { Button } from './ui/button.jsx'
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from './ui/sheet.jsx'

function Navigation({ projectRoute, session, onNavigate }) {
  const { projectId, view } = projectRoute
  const links = [
    { label: session.user.role==='ADMIN' ? 'Administration':session.user.role === 'CLIENT' ? 'My projects':'Dashboard', icon: LayoutDashboard, href: '#/app', active: view === 'dashboard' && !projectRoute.section },
    ...(session.user.role === 'DESIGNER' ? [
      {label:'Clients',icon:Users,href:'#/app/clients',active:projectRoute.section === 'clients' || projectRoute.section === 'projects'},
    ] : []),
    ...(session.user.role === 'ADMIN' ? [{label:'Clients',icon:Users,href:'#/app/clients',active:view === 'dashboard' && Boolean(projectRoute.section)}] : []),
    { label: session.user.role==='ADMIN' ? 'Admin settings':'User settings', icon: Settings, href: '#/app/settings', active: view === 'settings' },
  ]
  return <>
    <a className="studio-brand" href="#/app" onClick={onNavigate} aria-label="VED project dashboard">
      <img src={vedLogo} alt="VED Electrical Services" /><span>Electrical workspace<small className="mono">PLAN · REVIEW · ESTIMATE</small></span>
    </a>
    <nav className="studio-navigation" aria-label="Workspace navigation">
      <p className="mono">WORKSPACE</p>
      {session.user.role==='CLIENT' ? <span className="studio-project-context">Client portal<small>Your authorized projects</small></span> : projectId ? <a className="studio-project-context" href={getProjectHref(projectId)} onClick={onNavigate}>Project {projectId}<small>Floors &amp; plans</small></a>
        : <span className="studio-project-context studio-nav-unavailable">No project selected<small>Open a project to continue</small></span>}
      {links.map(({ label, icon: Icon, href, active }) => href
        ? <a key={label} href={href} onClick={onNavigate} aria-current={active ? 'page' : undefined}><Icon aria-hidden="true" /><span>{label}</span></a>
        : <button key={label} type="button" className="studio-nav-unavailable" disabled title="Open a project to access cost estimation"><Icon aria-hidden="true" /><span>{label}</span></button>)}
    </nav>
    <div className="studio-boundary"><ShieldCheck aria-hidden="true" /><div><strong>{session.user.role==='CLIENT'?'Read-only client view':'Local planning workspace'}</strong><p>{session.user.role==='CLIENT'?'Approved layouts and published estimates.':'Editable planning draft. Originals preserved.'}</p></div></div>
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
