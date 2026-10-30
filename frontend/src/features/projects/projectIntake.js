export const SERVICE_TYPES = [
  ['new_construction', 'New construction'], ['renovation', 'Renovation'],
  ['electrical_installation', 'Electrical installation'], ['data_installation','Data installation'], ['cctv_installation','CCTV installation'], ['maintenance_repair', 'Maintenance / repair'], ['other', 'Other'],
]
export const BLUEPRINT_AVAILABILITY = [['available_now', 'Available now'], ['later', 'Later'], ['unavailable', 'Unavailable']]
export const LAYOUT_TYPES=[['lighting','Lighting layout'],['power','Power layout'],['data','Data layout']]

export function intakeValues(project = {}) {
  return { name: project.name || '', clientName: project.client_name || '', location: project.location || '',
    allocatedBudget:project.allocated_budget ?? '',contactNumber: project.contact_number || '',layoutType:project.layout_type || '',serviceType: project.service_type || '',serviceTypes:project.service_types || (project.service_type?[project.service_type]:[]),
    serviceTypeOther: project.service_type_other || '', preferredStartDate: project.preferred_start_date || '',
    blueprintAvailability: project.blueprint_availability || '' }
}

export function intakePayload(values, includeEmpty = false) {
  const result = { name: values.name.trim(), client_name: values.clientName.trim() || (includeEmpty ? null : ''), location: values.location.trim() || (includeEmpty ? null : '') }
  const services=values.serviceTypes || (values.serviceType?[values.serviceType]:[])
  if(values.allocatedBudget!=='' && values.allocatedBudget!=null)result.allocated_budget=String(values.allocatedBudget)
  result.service_types=services
  result.layout_type=values.layoutType || null
  const optional = { contact_number: values.contactNumber.trim(), service_type: services[0] || null,
    service_type_other: services.includes('other') ? values.serviceTypeOther.trim() : '',
    preferred_start_date: values.preferredStartDate, blueprint_availability: values.blueprintAvailability }
  for (const [key, value] of Object.entries(optional)) if (value || includeEmpty) result[key] = value || null
  return result
}

export function layoutValues(value){return Array.isArray(value)?value:value?[value]:[]}
