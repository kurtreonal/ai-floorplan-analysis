import { useState } from 'react'
import { DrawingRegionPanel } from './DrawingRegionPanel.jsx'
import { Button } from '../../components/ui/button.jsx'
import { sourceViewChoices } from './sourceViewChoices.js'

export function SourceViewsPanel({ record, region, onRegionChange, onSelectRegion, onFreezeRegion, embedded=false, ...context }) {
  const [locked, setLocked] = useState(false)
  const choices = sourceViewChoices(record)
  if (!choices.length && !embedded) return null
  const content=<>
    <p>Select just one plan, such as lighting or power. Keep notes, legends and NTS diagrams outside the selection.</p>
    <div className="demo-add-actions">{choices.map((choice, index) =>
      <Button key={`${choice.label}-${index}`} variant="outline" disabled={locked}
        onClick={() => onRegionChange({ ...choice.region })}>Use {choice.label}</Button>)}</div>
    <DrawingRegionPanel record={record} region={region} onRegionChange={onRegionChange} compact={embedded}
      onSelectRegion={onSelectRegion} onFreezeRegion={value => { setLocked(Boolean(value)); onFreezeRegion?.(value) }} {...context} />
  </>
  return embedded ? <section className="studio-plan-area">{content}</section>
    : <details className="demo-approval-panel"><summary>Choose plan area</summary>{content}</details>
}
