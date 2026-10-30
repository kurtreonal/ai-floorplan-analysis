import { API_BASE_URL } from './auth.js'

function identifier(value) {
  if (!Number.isSafeInteger(value) || value <= 0) throw new Error('Invalid BOM identifier.')
}

function scopeQuery(floorPlanId, processingJobId, conduitMaterialId, paperSize, wireMaterialId, customWidthMm, customHeightMm, wireMetersPerUnit, wirePricePerMeter, conduitPricePerMeter, scaleDenominator, deviceMaterials, purchasePricing) {
  if (floorPlanId != null) identifier(floorPlanId)
  if (processingJobId != null) {
    identifier(processingJobId)
    if (floorPlanId == null) throw new Error('A plan is required for a job-scoped BOM.')
  }
  if (conduitMaterialId != null) identifier(conduitMaterialId)
  if (wireMaterialId != null) identifier(wireMaterialId)
  if (wireMetersPerUnit != null && (!Number.isFinite(wireMetersPerUnit) || wireMetersPerUnit <= 0 || wireMetersPerUnit > 100000 || wireMaterialId == null)) throw new Error('Choose a wire product and enter a valid purchase length.')
  if (wirePricePerMeter != null && (!Number.isFinite(wirePricePerMeter) || wirePricePerMeter < 0 || wirePricePerMeter > 1000000000)) throw new Error('Invalid custom wire price.')
  if (conduitPricePerMeter != null && (!Number.isFinite(conduitPricePerMeter) || conduitPricePerMeter < 0 || conduitPricePerMeter > 1000000000)) throw new Error('Invalid custom conduit price.')
  if (scaleDenominator != null && (!Number.isFinite(scaleDenominator) || scaleDenominator<1 || scaleDenominator>100000 || floorPlanId==null)) throw new Error('Enter a valid plan scale denominator.')
  if (paperSize != null && (!['A5','A4','A3','A2','A1','A0','CUSTOM'].includes(paperSize) || floorPlanId == null)) {
    throw new Error('Paper-size assumptions require a specific plan and standard paper size.')
  }
  if (paperSize === 'CUSTOM') {
    if (![customWidthMm,customHeightMm].every(value => Number.isFinite(value) && value > 0 && value <= 10000)) throw new Error('Enter custom sheet width and height in millimetres.')
  } else if (customWidthMm != null || customHeightMm != null) throw new Error('Custom dimensions require custom paper size.')
  const parts=[]
  if(purchasePricing && Object.keys(purchasePricing).length) parts.push(`purchase_pricing=${encodeURIComponent(JSON.stringify(purchasePricing))}`)
  if(deviceMaterials && Object.keys(deviceMaterials).length){
    if(Object.keys(deviceMaterials).length>200)throw new Error('Choose at most 200 device groups.')
    for(const [key,value] of Object.entries(deviceMaterials)){
      if(!/^\d+$/.test(key))throw new Error('Invalid device group.')
      identifier(value)
    }
    parts.push(`device_materials=${encodeURIComponent(JSON.stringify(deviceMaterials))}`)
  }
  if (floorPlanId != null) parts.push(`floor_plan_id=${floorPlanId}`)
  if (processingJobId != null) parts.push(`processing_job_id=${processingJobId}`)
  if (conduitMaterialId != null) parts.push(`conduit_material_id=${conduitMaterialId}`)
  if (paperSize != null) parts.push(`paper_size=${paperSize}`)
  if (wireMaterialId != null) parts.push(`wire_material_id=${wireMaterialId}`)
  if (paperSize === 'CUSTOM') parts.push(`custom_width_mm=${customWidthMm}`,`custom_height_mm=${customHeightMm}`)
  if (wireMetersPerUnit != null) parts.push(`wire_meters_per_unit=${wireMetersPerUnit}`)
  if (wirePricePerMeter != null) parts.push(`wire_price_per_meter=${wirePricePerMeter}`)
  if (conduitPricePerMeter != null) parts.push(`conduit_price_per_meter=${conduitPricePerMeter}`)
  if (scaleDenominator != null) parts.push(`scale_denominator=${scaleDenominator}`)
  return parts.length ? `?${parts.join('&')}` : ''
}

export async function fetchBOM(projectId, { signal, floorPlanId, processingJobId, conduitMaterialId, paperSize, wireMaterialId, customWidthMm, customHeightMm, wireMetersPerUnit, wirePricePerMeter, conduitPricePerMeter, scaleDenominator, draftPreview,deviceMaterials,purchasePricing } = {}) {
  identifier(projectId)
  const query = scopeQuery(floorPlanId,processingJobId,conduitMaterialId,paperSize,wireMaterialId,customWidthMm,customHeightMm,wireMetersPerUnit,wirePricePerMeter,conduitPricePerMeter,scaleDenominator,deviceMaterials,purchasePricing)
  const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/bom${draftPreview ? '/preview' : ''}${query}`, { credentials: 'include', signal,
    ...(draftPreview ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(draftPreview)} : {}) })
  if (!response.ok) throw new Error('Bill of materials is unavailable. Check project access and try again.')
  const body = await response.json()
  if (!body || body.project_id !== projectId || !Array.isArray(body.components) || !Array.isArray(body.layouts)
    || !Array.isArray(body.missing_layout_floors) || !['measured', 'unavailable'].includes(body.route_state)) throw new Error('Invalid BOM response.')
  return body
}

export async function downloadDraftBOM(projectId, {signal, floorPlanId, processingJobId, conduitMaterialId, paperSize, wireMaterialId, customWidthMm, customHeightMm,wireMetersPerUnit,wirePricePerMeter,conduitPricePerMeter,scaleDenominator,draftPreview,deviceMaterials,purchasePricing} = {}) {
  identifier(projectId)
  const query = scopeQuery(floorPlanId,processingJobId,conduitMaterialId,paperSize,wireMaterialId,customWidthMm,customHeightMm,wireMetersPerUnit,wirePricePerMeter,conduitPricePerMeter,scaleDenominator,deviceMaterials,purchasePricing)
  const path = draftPreview ? `/bom/preview${query}${query ? '&' : '?'}download=true&format=xlsx` : `/bom.csv${query}${query ? '&' : '?'}format=xlsx`
  const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}${path}`, {credentials:'include',signal,
    ...(draftPreview ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(draftPreview)} : {})})
  if (!response.ok) throw new Error('Draft BOM download is unavailable.')
  return response.blob()
}

export async function downloadBOM(projectId, estimateId, { signal } = {}) {
  identifier(projectId); identifier(estimateId)
  const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/estimates/${estimateId}/bom.csv?format=xlsx`, { credentials: 'include', signal })
  if (!response.ok) throw new Error('BOM download is unavailable. Check project access and try again.')
  return response.blob()
}
