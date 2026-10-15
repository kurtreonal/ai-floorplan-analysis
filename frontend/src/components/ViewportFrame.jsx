import { useEffect, useRef, useState } from 'react'
import { Maximize, Minimize } from 'lucide-react'
import { Button } from './ui/button.jsx'

export function ViewportFrame({ title, status, children }) {
  const frame = useRef(null)
  const trigger = useRef(null)
  const [expanded, setExpanded] = useState(false)
  const [fallback, setFallback] = useState(false)
  useEffect(() => {
    function changed() {
      if (document.fullscreenElement !== frame.current) {
        setExpanded(false)
        trigger.current?.focus()
      }
    }
    document.addEventListener('fullscreenchange', changed)
    return () => document.removeEventListener('fullscreenchange', changed)
  }, [])
  useEffect(() => {
    if (!expanded) return undefined
    const priorOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    function escape(event) { if (event.key === 'Escape') { setExpanded(false); setFallback(false); trigger.current?.focus() } }
    document.addEventListener('keydown', escape)
    return () => { document.body.style.overflow = priorOverflow; document.removeEventListener('keydown', escape) }
  }, [expanded])
  async function toggle() {
    if (expanded) {
      if (document.fullscreenElement === frame.current) await document.exitFullscreen?.()
      setExpanded(false); setFallback(false); trigger.current?.focus()
      return
    }
    setExpanded(true)
    try {
      if (!frame.current.requestFullscreen) throw new Error('unsupported')
      await frame.current.requestFullscreen()
    } catch { setFallback(true) }
  }
  return <section ref={frame} className={`studio-viewport-frame ${expanded && fallback ? 'is-expanded' : ''}`} aria-label={title}>
    <div className="studio-viewport-heading">
      <span>{title}</span>{expanded && status && <span role="status">{status}</span>}
      <Button ref={trigger} variant="outline" size="sm" aria-pressed={expanded} onClick={toggle}>
        {expanded ? <Minimize aria-hidden="true" /> : <Maximize aria-hidden="true" />}
        {expanded ? 'Exit fullscreen' : `Fullscreen ${title}`}
      </Button>
    </div>
    {children}
  </section>
}
