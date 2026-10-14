import { useState } from 'react'
import { DrawingRegionPanel } from './DrawingRegionPanel.jsx'
import { Button } from '../../components/ui/button.jsx'
import { sourceViewChoices } from './sourceViewChoices.js'

export function SourceViewsPanel({ record, region, onRegionChange, onSelectRegion, onFreezeRegion, ...context }) {
  const [locked, setLocked] = useState(false)
  const choices = sourceViewChoices(record)
  if (!choices.length) return null
  return <details className="demo-approval-panel">
    <summary>Separate floor views · {choices.length} partial proposals</summary>
    <p>These views share page coordinates, not a physical floor or circuit. Region boundaries need review.
      Save this 2D draft freely. For measured publication, process one view for the intended project floor;
      check or expand its rectangle to include missing perimeter areas.</p>
    <div className="demo-add-actions">{choices.map((choice, index) =>
      <Button key={`${choice.label}-${index}`} variant="outline" disabled={locked}
        onClick={() => onRegionChange({ ...choice.region })}>Use {choice.label}</Button>)}</div>
    <DrawingRegionPanel record={record} region={region} onRegionChange={onRegionChange}
      onSelectRegion={onSelectRegion} onFreezeRegion={value => { setLocked(Boolean(value)); onFreezeRegion?.(value) }} {...context} />
  </details>
}
