import { useContext, useEffect, useRef, useState } from 'react'
import { Maximize, Minimize } from 'lucide-react'
import { Button } from './ui/button.jsx'
import { ViewportContext } from './viewportContext.js'

export function ViewportFullscreenButton() {
  const viewport = useContext(ViewportContext)
  if (!viewport) return null
  const {expanded, title, toggle} = viewport
  return <Button className="studio-viewport-expand" variant="outline" size="icon"
    aria-label={expanded ? 'Exit fullscreen' : `Fullscreen ${title}`}
    title={expanded ? 'Exit workspace fullscreen (Esc)' : 'Expand workspace — browser stays visible'}
    aria-pressed={expanded} onClick={event => toggle(event.currentTarget)}>
    {expanded ? <Minimize aria-hidden="true" /> : <Maximize aria-hidden="true" />}
  </Button>
}

export function ViewportFrame({ title, status, children }) {
  const frame = useRef(null)
  const trigger = useRef(null)
  const [expanded, setExpanded] = useState(false)
  useEffect(() => {
    if (!expanded) return undefined
    const priorOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    function escape(event) { if (event.key === 'Escape') { setExpanded(false); trigger.current?.focus() } }
    document.addEventListener('keydown', escape)
    return () => { document.body.style.overflow = priorOverflow; document.removeEventListener('keydown', escape) }
  }, [expanded])
  function toggle(button) {
    trigger.current = button
    setExpanded(value => !value)
    trigger.current?.focus()
  }
  return <ViewportContext.Provider value={{expanded,title,toggle}}><section ref={frame} className={`studio-viewport-frame ${expanded ? 'is-expanded' : ''}`} aria-label={title}>
    {expanded && status && <span className="sr-only" role="status">{status}</span>}
    {children}
  </section></ViewportContext.Provider>
}
