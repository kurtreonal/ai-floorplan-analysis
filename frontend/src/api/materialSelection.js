import {API_BASE_URL} from './auth.js'

export async function saveMaterialSelection(projectId,{floorPlanId,expectedVersion,settings,requestId}) {
  const response=await fetch(`${API_BASE_URL}/api/projects/${projectId}/client-pricing/item-assignments/materials`,{
    credentials:'include',method:'PUT',headers:{'Content-Type':'application/json',Accept:'application/json'},
    body:JSON.stringify({floor_plan_id:floorPlanId ?? null,expected_version:expectedVersion,request_id:requestId,settings}),
  })
  const data=await response.json().catch(()=>null)
  if(!response.ok){
    if(response.status===401)window.location.replace('#/signin?reason=session-expired')
    const message=data?.detail?.error?.message
    throw new Error(typeof message==='string' ? message:'Could not save material choices. Reload and try again.')
  }
  return data
}
