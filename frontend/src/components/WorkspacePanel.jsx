import { useState } from 'react'
import { Button } from './ui/button.jsx'

export function WorkspacePanel({ title, className = '', labelledBy, children }) {
  const [open, setOpen] = useState(true)
  return <aside className={`studio-collapsible-panel ${className}`} data-collapsed={!open}>
    <Button variant="ghost" size="sm" aria-expanded={open} aria-label={`${open ? 'Close' : 'Reopen'} ${title}`} onClick={() => setOpen(!open)}>
      {open ? `Close ${title}` : `Open ${title}`}
    </Button>
    <div hidden={!open} role={labelledBy ? 'region' : undefined} aria-labelledby={labelledBy}>{children}</div>
  </aside>
}
