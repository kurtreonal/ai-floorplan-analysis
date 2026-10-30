import {useEffect,useRef} from 'react'
import {Button} from '../../components/ui/button.jsx'
import {SheetControls,DisplayPaperControls} from './SheetControls.jsx'
import {SourceViewsPanel} from './SourceViewsPanel.jsx'
import {X} from 'lucide-react'
import {WorkspaceGuide} from './WorkspaceGuide.jsx'

export function ScalePanel({open,onOpenChange,section,model,context,canSave,onUseRuler,onSelectArea,record,region,onRegionChange,
  onFreezeRegion,projectId,projectFloorId,floorPlanId,unsaved,onSaveDraft,draft}) {
  const needsArea=Boolean(context?.multiple_scale_views)
  const panel=useRef(null),wasOpen=useRef(false)
  useEffect(()=>{
    if(open){
      const selector=section==='view' ? '[data-select-plan-area]':section==='layout' ? 'select[aria-label="Display paper"]':section==='heights'?'input[aria-label="Ceiling height"]':'[data-automatic-setup]'
      ;(panel.current?.querySelector(selector) || panel.current)?.focus()
    }else if(wasOpen.current)document.querySelector('[data-scale-button]')?.focus()
    wasOpen.current=open
  },[open,section])
  // Keep processing controls mounted while closed so active jobs and retries survive.
  return <aside ref={panel} hidden={!open} className="studio-scale-panel" role="dialog" aria-modal="false" tabIndex={-1}
    aria-labelledby="scale-panel-title" aria-describedby="scale-panel-description" onKeyDown={event=>{
      if(event.key==='Escape'){event.stopPropagation();onOpenChange(false)}
    }}>
      <header><h2 id="scale-panel-title">{section==='layout' ? 'Display / print layout':'Plan measurements'}</h2><Button variant="ghost" size="icon" aria-label="Close scale settings" onClick={()=>onOpenChange(false)}><X size={18} aria-hidden="true"/></Button></header>
      <p id="scale-panel-description">{section==='layout' ? 'Arrange the page frame without changing measurements.':'One setup for 2D, 3D and material quantities.'}</p>
      <WorkspaceGuide section="measurements"/>
      <section aria-label="Edit drawing scale">
        {section==='layout' ? <DisplayPaperControls model={model} canSave={canSave}/>:<SheetControls model={model} context={context} canSave={canSave} draft={draft} needsArea={needsArea} onImproveAccuracy={onUseRuler} advancedOpen={section==='heights'}/>}
      </section>
      {needsArea && section!=='layout' && <section className="studio-scale-plan-section" aria-labelledby="scale-plan-area-title">
        <h3 id="scale-plan-area-title">Choose the plan to measure</h3>
        <SourceViewsPanel embedded record={record} region={region} onRegionChange={onRegionChange} onSelectRegion={onSelectArea}
          onFreezeRegion={onFreezeRegion} projectId={projectId} projectFloorId={projectFloorId} floorPlanId={floorPlanId}
          unsaved={unsaved} onSaveDraft={onSaveDraft}/>
      </section>}
  </aside>
}
