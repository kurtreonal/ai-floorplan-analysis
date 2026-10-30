import {Button} from '../../components/ui/button.jsx'
import {X} from 'lucide-react'
import {wiringCheck} from './wiringCheck.js'
import {useEffect,useRef} from 'react'
import {duplicateSourceTraces} from './traceRepairs.js'

export function WiringCheckPanel({draft,candidate,onClose,onSelect,onRepair,onRemoveDuplicate,onRestorePanel,estimateConnections=false}) {
  const segments=candidate.payload.observed_routes?.segments || []
  const rows=wiringCheck(draft.wirings || [],segments,draft.symbols)
  const duplicates=duplicateSourceTraces(draft.wirings||[])
  const problems=rows.filter(row=>row.broken || row.open.length || row.proposal || row.wire.assignment_state==='unresolved')
    .sort((a,b)=>Number(b.wire.assignment_state==='unresolved')-Number(a.wire.assignment_state==='unresolved'))
  const panel=useRef(null)
  useEffect(()=>{panel.current?.focus();return ()=>document.querySelector('[data-check-wiring]')?.focus()},[])
  const removed=segments.filter(s=>draft.wirings.some(w=>w.id===s.id && w.disposition==='rejected'))
  const removedPanels=draft.wirings.filter(w=>w.origin==='generated'&&w.disposition==='rejected'&&/home.?run/i.test(draft.symbols.find(s=>s.id===w.source_device_id)?.class_name||''))
  return <aside ref={panel} tabIndex={-1} className="studio-scale-panel" role="dialog" aria-modal="false" aria-label="Check wiring" onKeyDown={e=>{if(e.key==='Escape'){e.stopPropagation();onClose()}}}>
    <header><h2>Check wiring</h2><Button variant="ghost" size="icon" aria-label="Close wiring check" onClick={onClose}><X size={18}/></Button></header>
    <p>Select a wire to open its settings. The field to change and the loose endpoint will be highlighted in orange.</p>
    {duplicates.length>0&&<section className="wiring-duplicate-repairs"><h3>Overlapping traces</h3><p>These paths repeat an existing source line. Removing a duplicate keeps the longer path and its connections. Undo is available.</p>{duplicates.map(row=><div key={row.id}><Button variant="outline" onClick={()=>onSelect({kind:'wiring',id:row.id})}>{row.id}<small>Repeats {row.retainedId}</small></Button>{onRemoveDuplicate&&<Button variant="outline" onClick={()=>onRemoveDuplicate(row.id)}>Remove duplicate</Button>}</div>)}</section>}
    {removedPanels.length>0&&onRestorePanel&&<details><summary>Removed panel routes ({removedPanels.length})</summary><p>These saved suggestions were removed from this draft. Restore one to review it again.</p>{removedPanels.map(w=><Button key={w.id} variant="outline" onClick={()=>onRestorePanel(w.id)}>Restore {w.id}</Button>)}</details>}
    <div className="wiring-check-list">{problems.map(({wire:w,open,proposal,broken})=><Button key={w.id} variant="outline" onClick={()=>{if(onRepair)onRepair(w.id);else{onSelect({kind:'wiring',id:w.id});onClose()}}}>
      <span>{w.id}</span><small>{!w.installation_method || w.installation_method==='unknown' ? 'Choose Ceiling or Under floor':broken ? 'Replace the missing device connection':open.length ? `${open.includes(0)?'Start':'End'} point: choose a device or snap to a wire`:w.assignment_state==='unresolved' ? estimateConnections?'Uses estimated defaults · review connections':'Confirm endpoints or use estimated defaults':proposal?'Suggested route · review before adding':'Review this connection'}</small>
    </Button>)}</div>
    {removed.length>0 && <small>{removed.length} extracted paths were removed from this draft; dashed grey remains visible for comparison.</small>}
    {!problems.length && <p>{rows.length?'No open endpoints or missing device links.':'No active wiring paths.'}</p>}
    <details><summary>Drawing comparison</summary><p>Orange is the editable draft. Dashed grey is extracted source geometry. Inspect bends and branches against the original when reviewing trace completeness.</p></details>
  </aside>
}
