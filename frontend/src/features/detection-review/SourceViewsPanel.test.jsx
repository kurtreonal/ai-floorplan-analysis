/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
vi.mock('./DrawingRegionPanel.jsx', () => ({ DrawingRegionPanel: () => <div>Safe existing region processor</div> }))
import { SourceViewsPanel } from './SourceViewsPanel.jsx'
import { sourceViewChoices } from './sourceViewChoices.js'

afterEach(cleanup)
const record = { candidate: { payload: { warnings: [{ code: 'separate_source_views' }],
  source_plane: { width_pixels: 600, height_pixels: 400 } }, provenance: { inference_parameters: [
    { name: 'source-view-regions', value: JSON.stringify([
      { label: 'MEZZANINE', region: { x: 350, y: 50, width: 200, height: 200 } },
      { label: 'GROUND FLOOR', region: { x: 20, y: 50, width: 250, height: 250 } },
    ]) },
  ] } } }

it('offers distinct alphabetized partial scopes without writing or approving the draft', () => {
  const onRegionChange = vi.fn(), before = structuredClone(record)
  render(<SourceViewsPanel record={record} onRegionChange={onRegionChange} />)
  expect(screen.getAllByRole('button').map(b => b.textContent)).toEqual(['Use GROUND FLOOR', 'Use MEZZANINE'])
  fireEvent.click(screen.getByRole('button', { name: 'Use MEZZANINE' }))
  expect(onRegionChange).toHaveBeenCalledWith({ x: 350, y: 50, width: 200, height: 200 })
  expect(screen.getByText(/not a physical floor or circuit/)).toBeTruthy()
  expect(record).toEqual(before)
})

it('does not expose region controls on ordinary drawings or trust invalid provenance', () => {
  const ordinary = { candidate: { payload: { warnings: [] } } }
  expect(sourceViewChoices(ordinary)).toEqual([])
  const broken = structuredClone(record)
  broken.candidate.provenance.inference_parameters[0].value = 'invalid JSON'
  expect(sourceViewChoices(broken)).toEqual([])
  broken.candidate.provenance.inference_parameters[0].value = JSON.stringify([
    { label: 'A', region: { x: -5, y: 0, width: 20, height: 20 } },
    { label: 'B', region: { x: 0, y: 0, width: 900, height: 20 } },
  ])
  expect(sourceViewChoices(broken)).toEqual([])
})
