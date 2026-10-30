import { useCallback, useEffect, useMemo, useState } from 'react'
import { appendDrawingVertex } from '../detection-review/connectedWiring.js'
import { drawingWorkPlane, drawingTargetVertex, spatialDrawingTarget, usesRelativeHeight } from './workPlaneDrawing.js'

export function useSpatialDrawing({tool,scene,draft,context,presentations,method,editingSession,onAddWire,onAddWall,onPendingChange,onToolChange,snapping,disabled,setupRevision=0}) {
  const [storedSettings,setSettings]=useState({revision:setupRevision,values:{elevation:'',circuit:'',thickness:'',height:'',length:'',axis:'none'}})
  // A setup reset must not reuse a stale absolute-datum number as an AFF height.
  const settings=storedSettings.revision===setupRevision ? storedSettings.values : {...storedSettings.values,elevation:''}
  const [session,setSession]=useState(null)
  const [hasDrawn,setHasDrawn]=useState(false)
  const [hover,setHover]=useState(null)
  const [pending,setPending]=useState(null)
  const [error,setError]=useState(null)
  const active=['wire','draw'].includes(tool)
  const vertices=useMemo(()=>session&&session.tool===tool&&session.id===editingSession ? session.vertices : [],[session,tool,editingSession])
  let config=null,reason=null
  if(active)try{config=drawingWorkPlane(tool,settings,context,scene,method)}catch(e){reason=e.message}
  const enabled=active&&config!==null&&!disabled
  const activePending=pending&&pending.draft===draft&&pending.tool===tool&&pending.id===editingSession?pending:null
  const clear=useCallback(()=>{setSession(null);setPending(null);setHover(null);setError(null);onPendingChange?.(false)},[onPendingChange])
  const cancel=useCallback(()=>{clear();onToolChange?.('select')},[clear,onToolChange])
  const finish=useCallback(()=>{
    if(!enabled)return
    if(tool==='wire'&&vertices.length>=2) {
      if(onAddWire?.(vertices.map(v=>v.point),vertices,config?.wireAttributes || {elevation_meters:config?.elevation,circuit_id:config?.circuitId})===false)return
    }
    cancel()
  },[enabled,tool,vertices,onAddWire,config,cancel])
  useEffect(()=>{
    if(!active)return
    const key=event=>{
      if(event.target?.closest?.('input,select,textarea,[contenteditable="true"]'))return
      if(event.key!=='Escape'&&event.target?.closest?.('button'))return
      if(!['Enter','Escape','Backspace'].includes(event.key))return
      event.preventDefault()
      if(event.key==='Escape')cancel()
      else if(event.key==='Enter')finish()
      else {const next=vertices.slice(0,-1);setSession({id:editingSession,tool,vertices:next});setPending(null);onPendingChange?.(next.length>0)}
    }
    window.addEventListener('keydown',key)
    return()=>window.removeEventListener('keydown',key)
  },[active,cancel,finish,vertices,editingSession,tool,onPendingChange])
  function addVertex(target) {
    if(!enabled)return
    const point=target.point
    if(![point.x,point.y].every(Number.isFinite)||point.x<0||point.y<0||point.x*scene.sourceScale>scene.width||point.y*scene.sourceScale>scene.depth){setError('The drawing point is outside the source page.');return}
    setHasDrawn(true)
    if(tool==='draw'&&vertices.length) {
      const start=vertices.at(-1).point
      if(Math.hypot(start.x-point.x,start.y-point.y)<1e-6)return
      if(onAddWall?.({start,end:point,thickness_meters:config.thickness,height_meters:config.height,
        estimated_thickness_pixels:config.thickness*config.ppm})===false)return
      setSession({id:editingSession,tool,vertices:[{point}]})
    } else {
      const next=appendDrawingVertex(vertices,point,target.snap)
      setSession({id:editingSession,tool,vertices:next})
    }
    setPending(null);setHover(null);setError(null);onPendingChange?.(true)
  }
  function pointer(raw,options,commit=false) {
    if(!enabled || activePending)return
    const target=spatialDrawingTarget(raw,{tool,vertices,draft,presentations,config,method,snapping,...options})
    setHover({...target,tool,id:editingSession})
    if(commit) {
      if(target.choices?.length>1){setPending({choices:target.choices,draft,tool,id:editingSession});return}
      addVertex(target)
    }
  }
  return {active,enabled,config,settings,relativeHeight:usesRelativeHeight(context),defaultRoutingHeight:method==='concealed_in_ceiling'?context?.service_height_above_floor_meters:null,keepCanvas:hasDrawn,reason:disabled?'Wait for the current save to finish.':reason,error,vertices,
    hover:hover&&hover.tool===tool&&hover.id===editingSession?hover:null,
    choices:activePending?.choices,
    setOption:(key,value)=>{if(!vertices.length){setSettings(previous=>({revision:setupRevision,values:{...previous.values,...(previous.revision!==setupRevision ? {elevation:''}:{}),[key]:value}}));setPending(null);setHover(null);setError(null)}},
    pointer,finish,cancel,clear,
    choose:target=>{if(activePending)addVertex(drawingTargetVertex(target))},
    preview:target=>setHover({...drawingTargetVertex(target),tool,id:editingSession}),cancelChoice:()=>{setPending(null);setHover(null)}}
}
