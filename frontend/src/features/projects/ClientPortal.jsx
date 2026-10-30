import {FolderOpen,Clock,CheckCircle2,Plus,ArrowLeft} from 'lucide-react'
import { lazy, Suspense, useEffect, useState } from 'react'
import { workflowRequest } from '../../api/clientWorkflow.js'
import { buildCanonicalScene } from '../viewer-3d/canonicalScene.js'
import { buildDraftRoomScene } from '../detection-review/draftRoomScene.js'
import { deviceFamily } from '../detection-review/devicePresentation.js'
import { DemoInterpretationCanvas as PlanCanvas } from '../detection-review/DemoInterpretationCanvas.jsx'
import { Button } from '../../components/ui/button.jsx'
import { Viewer3DErrorBoundary } from '../viewer-3d/Viewer3DErrorBoundary.jsx'
import {ClientPlanSubmission} from './ClientPlanSubmission.jsx'
import {ClientProjectTable} from './ClientProjectTable.jsx'
import {ApprovedClientBOM} from './ApprovedClientBOM.jsx'
const Canvas = lazy(() => import('../viewer-3d/Viewer3DCanvas.jsx').then(m => ({ default: m.Viewer3DCanvas })))

export function ClientPortal() {
  const [projects, setProjects] = useState([]), [publication, setPublication] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(true), [floor, setFloor] = useState('')
  const [view,setView] = useState('2d')
  const [submission,setSubmission]=useState(null),[refresh,setRefresh]=useState(0)
  useEffect(() => { const c = new AbortController(); workflowRequest('/client/projects', { signal: c.signal }).then(setProjects).catch(e => { if (e.name !== 'AbortError') setError(e.message) }).finally(() => { if (!c.signal.aborted) setBusy(false) }); return () => c.abort() }, [refresh])
  async function open(id) { setBusy(true); setError(''); setPublication(null)
    try { const data = await workflowRequest(`/client/projects/${id}/publication`); setPublication(data); setFloor(String(data.layouts[0]?.id || '')) } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const layout = publication?.layouts.find(x => String(x.id) === floor)
  let scene = null, approvedDraft = null, presentations = {}
  if (layout) { try {
    if (layout.kind === 'approved_draft') {
      approvedDraft = {...layout.draft,wirings:[...layout.draft.observed_wiring,...layout.draft.generated_wiring.map(w => ({...w,origin:'generated'}))]}
      presentations = Object.fromEntries(approvedDraft.symbols.map(s => [s.id,{name:s.class_name || 'Device',label:s.class_name || 'Device',family:deviceFamily(s.class_name)}]))
      scene = buildDraftRoomScene(approvedDraft,layout.width,layout.height,.8,presentations)
    } else scene = buildCanonicalScene(layout.geometry,layout.extension)
  } catch { /* A malformed historical layout must not expose another revision. */ } }
  return <section className="client-portal" aria-busy={busy}><header className="client-portal-heading"><div><span className="project-kicker">CLIENT WORKSPACE</span><h1>{publication ? publication.project.name : submission ? 'Send floor plans':'Your projects'}</h1><p>{publication?'Your Admin-published layouts and estimate.':submission?'Share your project details and files with VED.':'Track your requests and open the designs VED has published for you.'}</p></div>{!publication && !submission && <Button disabled={busy} onClick={()=>setSubmission({})}><Plus size={18}/>Send floor plans</Button>}{publication && <Button variant="outline" onClick={()=>setPublication(null)}><ArrowLeft size={16}/>Your projects</Button>}</header>
    {error && <p className="client-page-error" role="alert">{error}</p>}{busy && <p className="client-loading" role="status">Loading your workspace...</p>}
    {!publication && !submission && !busy && <div className="client-project-overview">{[[FolderOpen,'Projects',projects.length],[Clock,'In progress',projects.filter(project=>!project.approved).length],[CheckCircle2,'Ready to view',projects.filter(project=>project.approved).length]].map(([Icon,label,count])=><div key={label}><span><Icon size={18}/>{label}</span><strong>{count}</strong></div>)}</div>}
    {submission && <ClientPlanSubmission key={submission.id || 'new'} project={submission.id?submission:undefined} onSubmitted={()=>setRefresh(n=>n+1)} onClose={()=>{setSubmission(null);setRefresh(n=>n+1)}}/>}
    {!publication && !submission && !busy && <ClientProjectTable projects={projects} onOpen={open} onSubmit={setSubmission}/>}
    {publication && <><p className="client-publication-note">{publication.estimate?'Published':'Approved'} {new Date(publication.approved_at).toLocaleDateString()} - Read-only planning presentation</p>
      <label className="studio-field">Floor / approved layout<select value={floor} onChange={e => setFloor(e.target.value)}>{publication.layouts.map(x => <option key={x.id} value={x.id}>{x.floor_name || `Floor ${x.floor_id}`} · Version {x.version}</option>)}</select></label>
      {approvedDraft && <div className="workflow-dashboard-tabs" role="group" aria-label="Read-only layout view"><Button variant={view==='2d'?'default':'outline'} aria-pressed={view==='2d'} onClick={()=>setView('2d')}>2D layout</Button><Button variant={view==='3d'?'default':'outline'} aria-pressed={view==='3d'} onClick={()=>setView('3d')}>3D view</Button></div>}
      {scene ? <Viewer3DErrorBoundary projectId={publication.project.id}><Suspense fallback={<p>Loading presentation…</p>}><div className="workflow-client-view">{approvedDraft && view==='2d' ? <PlanCanvas key={layout.id} readOnlyPresentation width={layout.width} height={layout.height} draft={approvedDraft} tool="pan" layers={{source:false,walls:true,rooms:false,symbols:true,wirings:true,dimensions:false,names:false}} presentations={presentations}/> : <Canvas scene={scene} readOnlyPresentation estimated={layout.kind==='approved_draft'} projectLabel={publication.project.name}/>}</div></Suspense></Viewer3DErrorBoundary> : <p>This saved layout is available for VED review; its 3D preview needs an updated geometry version.</p>}
      {publication.estimate ? <ApprovedClientBOM estimate={publication.estimate}/> : <p>Layout approved. Ask VED Admin to publish the project BOM.</p>}
    </>}
  </section>
}
