import { Info } from 'lucide-react'
import './planInformation.css'

export function PlanInformation({ title, children }) {
  return <div className="studio-plan-information">
    <details onKeyDown={event => {
      if (event.key !== 'Escape') return
      event.stopPropagation()
      event.currentTarget.open = false
      event.currentTarget.querySelector('summary')?.focus()
    }}>
      <summary title="Plan information" aria-label="Plan information"><Info size={18} aria-hidden="true" /></summary>
      <div className="studio-plan-information-body"><h2>{title}</h2>{children}</div>
    </details>
  </div>
}
