export function PersonFields({person={}}) {
  return <>
    <div className="account-form-grid">
      <label>First name<input name="first_name" defaultValue={person.first_name || ''} required maxLength={80} autoComplete="given-name"/></label>
      <label>Middle name <small>Optional</small><input name="middle_name" defaultValue={person.middle_name || ''} maxLength={80} autoComplete="additional-name"/></label>
      <label>Last name<input name="last_name" defaultValue={person.last_name || ''} required maxLength={80} autoComplete="family-name"/></label>
    </div>
    {person.id && !person.first_name && <small>Existing name: {person.display_name}. Enter its separate parts to update this profile.</small>}
    <label>Phone number<input name="phone_number" type="tel" defaultValue={person.phone_number || ''} required minLength={7} maxLength={64} pattern="[+0-9() .\-]+" autoComplete="tel"/></label>
    <label>Location<input name="location" defaultValue={person.location || ''} required maxLength={500} autoComplete="street-address"/></label>
  </>
}
