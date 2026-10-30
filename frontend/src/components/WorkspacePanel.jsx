import { useState } from 'react'
import { Button } from './ui/button.jsx'
import { PanelLeftOpen, PanelRightOpen, X } from 'lucide-react'

export function WorkspacePanel({ title, className = '', labelledBy, children, open: controlledOpen, onOpenChange, defaultOpen = false }) {
  const [localOpen, setLocalOpen] = useState(defaultOpen)
  const open = controlledOpen ?? localOpen
  const right = /inspector|demo-review-tools/.test(className)
  const Icon = open ? X : right ? PanelRightOpen : PanelLeftOpen
  return <aside className={`studio-collapsible-panel ${className}`} data-collapsed={!open}>
    <Button className="studio-panel-toggle" variant="outline" size="icon" title={`${open ? 'Close' : 'Open'} ${title}`} aria-expanded={open} aria-label={`${open ? 'Close' : 'Reopen'} ${title}`} onClick={() => { setLocalOpen(!open); onOpenChange?.(!open) }}>
      <Icon size={16} aria-hidden="true" />
    </Button>
    <div hidden={!open} role={labelledBy ? 'region' : undefined} aria-labelledby={labelledBy}>{children}</div>
  </aside>
}
