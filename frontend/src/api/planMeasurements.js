import { API_BASE_URL } from './auth.js'

export async function planMeasurements(projectId,planId,{body,signal,processingJobId}={}) {
  const query=!body && processingJobId ? `?processing_job_id=${processingJobId}`:''
  const response=await fetch(`${API_BASE_URL}/api/projects/${projectId}/floor-plans/${planId}/measurement-settings${query}`,{
    method:body ? 'PUT':'GET',credentials:'include',signal,
    headers:{Accept:'application/json',...(body ? {'Content-Type':'application/json'}:{})},
    ...(body ? {body:JSON.stringify(body)}:{}),
  })
  if(!response.ok){
    const error=new Error(response.status===409 ? 'Measurements changed in another window. Reload settings to continue.':'Plan measurements could not be loaded or saved. Please retry.')
    error.status=response.status
    throw error
  }
  return response.json()
}
