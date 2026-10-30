import {LAYOUT_TYPES,layoutValues} from './projectIntake.js'

export function LayoutTypeChoices({value,onChange,disabled=false}){
  const selected=layoutValues(value)
  return <fieldset className="layout-type-choices" disabled={disabled}><legend>Layout types</legend><small>Select every layout included in this file.</small><div>{LAYOUT_TYPES.map(([id,label])=><label key={id}><input type="checkbox" checked={selected.includes(id)} onChange={event=>onChange(LAYOUT_TYPES.map(([key])=>key).filter(key=>key===id?event.target.checked:selected.includes(key)))}/>{label}</label>)}</div></fieldset>
}
