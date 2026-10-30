import { useState } from 'react'
import { AdminLegendPanel } from './AdminLegendPanel.jsx'
import { AdminMaterialImport } from './AdminMaterialImport.jsx'
import { AdminMaterialCatalog } from './AdminMaterialCatalog.jsx'
import { AdminAssemblies } from './AdminAssemblies.jsx'
import { Button } from '../../components/ui/button.jsx'
import { AdminUsers } from './AdminUsers.jsx'
import { AdminWiringPairs } from './AdminWiringPairs.jsx'
import { AdminActivity } from './AdminActivity.jsx'
import { AdminDraftReviews } from './AdminDraftReviews.jsx'
import { Users, ClipboardCheck, Cable, Shapes, Package, History, Settings, Coins } from 'lucide-react'
import './adminCatalog.css'

const sections = [
  {id:'clients',label:'Users',group:'Workspace',icon:Users},
  {id:'reviews',label:'Draft reviews',group:'Workspace',icon:ClipboardCheck},
  {id:'activity',label:'Activity log',group:'Workspace',icon:History},
  {id:'prices',label:'Material prices',group:'Catalog',icon:Coins},
  {id:'assemblies',label:'Device assemblies',group:'Catalog',icon:Package},
  {id:'pairs',label:'Wire & conduit',group:'Catalog',icon:Cable},
  {id:'legends',label:'Device legends',group:'Catalog',icon:Shapes},
]

export function AdminWorkspace(){
  const [view,setView]=useState('clients'),[showImport,setShowImport]=useState(false)
  return <section aria-label="Administration" className="admin-workspace">
    <header className="admin-workspace-heading"><div><span className="project-kicker">ADMINISTRATION</span><h1>Manage your workspace</h1><p>People, approvals and the materials behind every estimate.</p></div><a href="#/app/settings"><Settings size={16}/>Admin settings</a></header>
    <div className="admin-workspace-grid"><nav className="admin-section-nav" aria-label="Administration sections">{['Workspace','Catalog'].map(group=><div key={group}><h2>{group}</h2>{sections.filter(s=>s.group===group).map(({id,label,icon:Icon})=><Button key={id} aria-current={view===id?'page':undefined} onClick={()=>setView(id)} variant="ghost"><Icon size={18}/>{label}</Button>)}</div>)}</nav>
      <div className="admin-section-content">{view==='clients' && <AdminUsers/>}{view==='activity' && <AdminActivity/>}{view==='reviews' && <AdminDraftReviews/>}{view==='pairs' && <AdminWiringPairs/>}{view==='legends' && <AdminLegendPanel/>}<div hidden={view!=='prices'}>{view==='prices'&&<AdminMaterialCatalog onImport={()=>setShowImport(current=>!current)} onOpenAssemblies={()=>setView('assemblies')}/>}{view==='prices' && showImport && <section className="admin-import-panel"><header><h2>Import price workbook</h2><Button variant="ghost" onClick={()=>setShowImport(false)}>Close import</Button></header><AdminMaterialImport/></section>}</div>{view==='assemblies'&&<AdminAssemblies/>}</div>
    </div></section>
}
