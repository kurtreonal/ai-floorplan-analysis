import { useEffect, useRef } from 'react'
import { wiringTargetLabel } from './wiringTargetLabel.js'
import './wiringTargetChooser.css'

export function WiringTargetChooser({ choices, presentations, onPreview, onChoose, onCancel }) {
  const first = useRef(null)
  useEffect(() => {
    const previous = document.activeElement
    first.current?.focus()
    return () => { if (previous?.isConnected) previous.focus() }
  }, [])
  return <div className="wiring-target-chooser" role="group" aria-label="Choose connection target"
    onKeyDown={event => {
      if (['Escape','Enter',' '].includes(event.key)) event.stopPropagation()
      if (event.key === 'Escape') onCancel()
    }}>
    <div className="wiring-target-chooser-heading"><strong>Connect to</strong>
      <button type="button" aria-label="Cancel connection" onClick={onCancel}>×</button></div>
    <div className="wiring-target-chooser-options">
      {choices.map((target,index) => <button type="button" key={`${target.kind}:${target.symbolId || target.wireId}:${target.terminalId || index}`}
        ref={index === 0 ? first : null} onFocus={() => onPreview(target)} onMouseEnter={() => onPreview(target)}
        onClick={() => onChoose(target)}>{wiringTargetLabel(target,presentations)}</button>)}
    </div>
  </div>
}
