import { BLUEPRINT_AVAILABILITY, SERVICE_TYPES } from './projectIntake.js'

export function ProjectIntakeFields({ values, onChange, disabled = false }) {
  return <>
    <label><span>Project name</span><input name="name" value={values.name} onChange={onChange} required maxLength={255} autoComplete="off" disabled={disabled} /></label>
    <label><span>Client name <small>Optional</small></span><input name="clientName" value={values.clientName} onChange={onChange} maxLength={255} autoComplete="organization" disabled={disabled} /></label>
    <label><span>Contact number <small>Optional</small></span><input name="contactNumber" type="tel" value={values.contactNumber} onChange={onChange} maxLength={64} autoComplete="tel" disabled={disabled} /></label>
    <label><span>Location <small>Optional</small></span><input name="location" value={values.location} onChange={onChange} maxLength={500} autoComplete="street-address" disabled={disabled} /></label>
    <label><span>Project / service type</span><select name="serviceType" value={values.serviceType} onChange={onChange} disabled={disabled}>
      <option value="">Not specified</option>{SERVICE_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select></label>
    {values.serviceType === 'other' && <label><span>Other project / service type</span><input name="serviceTypeOther" value={values.serviceTypeOther} onChange={onChange} required maxLength={255} disabled={disabled} /></label>}
    <label><span>Preferred start date</span><input name="preferredStartDate" type="date" min="1000-01-01" max="9999-12-31" value={values.preferredStartDate} onChange={onChange} disabled={disabled} /></label>
    <label><span>Blueprint availability</span><select name="blueprintAvailability" value={values.blueprintAvailability} onChange={onChange} disabled={disabled}>
      <option value="">Not specified</option>{BLUEPRINT_AVAILABILITY.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select></label>
  </>
}
