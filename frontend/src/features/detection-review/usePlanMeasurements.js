import {useEffect,useRef,useState} from 'react'
import {planMeasurements} from '../../api/planMeasurements.js'

const displayFields=['display_paper_size','display_orientation','display_width_mm','display_height_mm']

export function usePlanMeasurements(projectId,planId,processingJobId) {
  const key=`${projectId}:${planId}:${processingJobId || ''}`
  const [state,setState]=useState(null),[reload,setReload]=useState(0)
  const request=useRef(null),pending=useRef(null)
  useEffect(()=>{
    const controller=new AbortController()
    planMeasurements(projectId,planId,{signal:controller.signal,processingJobId}).then(record=>{
      if(!controller.signal.aborted)setState({key,record,values:record.settings,status:'ready',error:''})
    }).catch(error=>{
      if(!controller.signal.aborted)setState({key,status:'error',error:error.message})
    })
    return ()=>{controller.abort();request.current?.abort()}
  },[projectId,planId,processingJobId,key,reload])
  const current=state?.key===key ? state:null
  return {
    values:current?.values,record:current?.record,error:current?.error,
    loading:!current,status:current?.status,
    dirty:Boolean(current?.record && JSON.stringify(current.values)!==JSON.stringify(current.record.settings)),
    reload:()=>setReload(value=>value+1),
    update:patch=>setState(previous=>previous?.key===key && previous.values ? {...previous,values:{...previous.values,...patch},status:'ready',error:''}:previous),
    async save(patch={}, {displayOnly=false,automatic=false}={}){
      if(!current?.record || current.status==='saving')return null
      const controller=new AbortController();request.current=controller
      const values=displayOnly
        ? {...current.record.settings,...Object.fromEntries(displayFields.map(k=>[k,current.values[k]]))}
        : automatic ? current.record.settings : {...current.values,...patch}
      const identity=JSON.stringify([key,current.record.revision,values,automatic])
      if(pending.current?.identity!==identity)pending.current={identity,id:crypto.randomUUID()}
      setState(previous=>({...previous,status:'saving',error:''}))
      try{
        const record=await planMeasurements(projectId,planId,{signal:controller.signal,
          body:{...values,use_automatic_setup:automatic,processing_job_id:processingJobId || null,expected_revision:current.record.revision,request_id:pending.current.id}})
        if(controller.signal.aborted)return null
        pending.current=null
        const nextValues=displayOnly
          ? {...current.values,...Object.fromEntries(displayFields.map(k=>[k,record.settings[k]]))}
          : record.settings
        setState({key,record,values:nextValues,status:JSON.stringify(nextValues)===JSON.stringify(record.settings) ? 'saved':'ready',error:''})
        return record
      }catch(error){
        if(!controller.signal.aborted)setState(previous=>({...previous,status:'error',error:error.message}))
        return null
      }
    },
  }
}
