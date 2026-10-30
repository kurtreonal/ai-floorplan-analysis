import { BLUEPRINT_AVAILABILITY, SERVICE_TYPES } from './projectIntake.js'

export function ProjectIntakeFields({ values, onChange, disabled = false, hideClient = false }) {
  return <>
    <label><span>Project name</span><input name="name" value={values.name} onChange={onChange} required maxLength={255} autoComplete="off" disabled={disabled} /></label>
    {!hideClient && <label><span>Client name <small>Optional</small></span><input name="clientName" value={values.clientName} onChange={onChange} maxLength={255} autoComplete="organization" disabled={disabled} /></label>}
    <label><span>Phone number</span><input name="contactNumber" type="tel" required minLength={7} pattern="[+0-9() .\-]+" value={values.contactNumber} onChange={onChange} maxLength={64} autoComplete="tel" disabled={disabled} /></label>
    <label><span>Location</span><input name="location" value={values.location} required onChange={onChange} maxLength={500} autoComplete="street-address" disabled={disabled} /></label>
    <label><span>Allocated budget (PHP)</span><input name="allocatedBudget" type="number" required min="0" max="999999999999.99" step="0.01" value={values.allocatedBudget} onChange={onChange} disabled={disabled}/><small>Admin can change this after the project is submitted.</small></label>
    <fieldset className="project-services" disabled={disabled}><legend>Project / installation services</legend><p>Select all that apply.</p><div>{SERVICE_TYPES.map(([value,label])=><label key={value}><input type="checkbox" checked={(values.serviceTypes || []).includes(value)} onChange={event=>onChange({target:{name:'serviceTypes',value:event.target.checked?[...(values.serviceTypes || []),value]:(values.serviceTypes || []).filter(x=>x!==value)}})}/>{label}</label>)}</div></fieldset>
    {(values.serviceTypes || []).includes('other') && <label><span>Other service</span><input name="serviceTypeOther" value={values.serviceTypeOther} onChange={onChange} required maxLength={255} disabled={disabled} /></label>}
    <label><span>Preferred start date</span><input name="preferredStartDate" type="date" min="1000-01-01" max="9999-12-31" value={values.preferredStartDate} onChange={onChange} disabled={disabled} /></label>
    <label><span>Blueprint availability</span><select name="blueprintAvailability" value={values.blueprintAvailability} onChange={onChange} disabled={disabled}>
      <option value="">Not specified</option>{BLUEPRINT_AVAILABILITY.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select></label>
  </>
}
