/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { DraftRoomPreview } from './DraftRoomPreview.jsx'
const capture = vi.hoisted(() => ({ props: null }))
vi.mock('../viewer-3d/Viewer3DCanvas.jsx', () => ({ Viewer3DCanvas: (props) => { capture.props = props; return <div>Scene</div> } }))
afterEach(cleanup)
it('toggles the roof independently, rescales physical presets and preserves pixel-space dragging', () => {
  const draft = { rooms: [], walls: [{ id: 'w', start: { x: 10, y: 10 }, end: { x: 90, y: 10 } }], symbols: [{ id: 's', center: { x: 50, y: 50 } }] }
  const before = structuredClone(draft), onUpdateSymbol = vi.fn()
  render(<DraftRoomPreview draft={draft} width={100} height={200} projectId={1} onUpdateSymbol={onUpdateSymbol} />)
  expect(capture.props.showRoof).toBe(false)
  expect(capture.props.scene.ceilingElevation).toBe(0.75)
  fireEvent.click(screen.getByRole('button', { name: 'Show roof' }))
  expect(capture.props.showRoof).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: 'Hide roof' }))
  expect(capture.props.showRoof).toBe(false)
  fireEvent.change(screen.getByLabelText('Source page long side (m)'), { target: { value: '20' } })
  expect(capture.props.scene.unitsPerMeter).toBe(0.5)
  expect(capture.props.scene.ceilingElevation).toBe(1.5)
  fireEvent.change(screen.getByLabelText('Wall height (m)'), { target: { value: '4' } })
  expect(capture.props.scene.ceilingElevation).toBe(2)
  capture.props.onMoveSymbol('s', { x: 3, y: 4 })
  expect(onUpdateSymbol).toHaveBeenCalledWith({ ...draft.symbols[0], center: { x: 60, y: 80 } })
  expect(draft).toEqual(before)
})
