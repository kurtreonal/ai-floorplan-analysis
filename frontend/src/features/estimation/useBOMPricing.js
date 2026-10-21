import { useEffect, useRef, useState } from 'react'
import { listProjectPrices, uploadAutomaticPrices } from '../../api/projectPricing.js'

// Upload is the application action. No catalog mapping or user approval stage.
export function useBOMPricing({projectId,floorId,disabled,onApplied,onVersionsChange}) {
  const sourceKey=`${projectId}:${floorId || 'project'}`
  const [state,setState]=useState({sourceKey,busy:false,error:'',uncertain:false,result:null})
  const controller=useRef(null),pending=useRef(null),inFlight=useRef(false)
  useEffect(()=>()=>{
    controller.current?.abort()
    controller.current=null;pending.current=null;inFlight.current=false
  },[sourceKey])
  useEffect(()=>{
    if(!onVersionsChange)return
    const request=new AbortController()
    listProjectPrices(projectId,{signal:request.signal}).then(rows=>{if(!request.signal.aborted)onVersionsChange(rows)}).catch(()=>{})
    return ()=>request.abort()
  },[projectId,onVersionsChange])
  async function execute(attempt) {
    if(inFlight.current || disabled || !attempt)return
    inFlight.current=true
    pending.current=attempt
    const request=new AbortController();controller.current=request
    setState({sourceKey,busy:true,error:'',uncertain:false,result:null})
    try {
      const result=await uploadAutomaticPrices(projectId,attempt.file,{signal:request.signal,requestId:attempt.requestId,floorId:attempt.floorId})
      if(request.signal.aborted)return
      pending.current=null
      setState({sourceKey,busy:false,error:'',uncertain:false,result})
      onApplied?.()
      // A read failure must not turn a successful atomic upload into a retry.
      if(onVersionsChange)listProjectPrices(projectId,{signal:request.signal})
        .then(rows=>{if(!request.signal.aborted)onVersionsChange(rows)}).catch(()=>{})
    } catch(error) {
      if(!request.signal.aborted){
        const uncertain=!error.status || error.status>=500
        if(!uncertain)pending.current=null
        setState({sourceKey,busy:false,error:error.message,uncertain,result:null})
      }
    } finally {
      if(controller.current===request)inFlight.current=false
    }
  }
  const current=state.sourceKey===sourceKey ? state : {busy:false,error:'',uncertain:false,result:null}
  return {...current,active:false,locked:current.busy || disabled || current.uncertain,
    scopeLabel:floorId ? `this floor (${floorId})`:'this project',
    uploaded:file=>{if(file && !pending.current)execute({file,requestId:crypto.randomUUID(),floorId})},
    retry:()=>execute(pending.current)}
}
