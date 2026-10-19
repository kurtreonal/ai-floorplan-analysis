export const SERVICE_TYPES = [
  ['new_construction', 'New construction'], ['renovation', 'Renovation'],
  ['electrical_installation', 'Electrical installation'], ['maintenance_repair', 'Maintenance / repair'], ['other', 'Other'],
]
export const BLUEPRINT_AVAILABILITY = [['available_now', 'Available now'], ['later', 'Later'], ['unavailable', 'Unavailable']]

export function intakeValues(project = {}) {
  return { name: project.name || '', clientName: project.client_name || '', location: project.location || '',
    contactNumber: project.contact_number || '', serviceType: project.service_type || '',
    serviceTypeOther: project.service_type_other || '', preferredStartDate: project.preferred_start_date || '',
    blueprintAvailability: project.blueprint_availability || '' }
}

export function intakePayload(values, includeEmpty = false) {
  const result = { name: values.name.trim(), client_name: values.clientName.trim() || (includeEmpty ? null : ''), location: values.location.trim() || (includeEmpty ? null : '') }
  const optional = { contact_number: values.contactNumber.trim(), service_type: values.serviceType,
    service_type_other: values.serviceType === 'other' ? values.serviceTypeOther.trim() : '',
    preferred_start_date: values.preferredStartDate, blueprint_availability: values.blueprintAvailability }
  for (const [key, value] of Object.entries(optional)) if (value || includeEmpty) result[key] = value || null
  return result
}
